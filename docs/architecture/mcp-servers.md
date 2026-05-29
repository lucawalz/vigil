# Vigil — MCP Servers

Four Go MCP servers run as long-lived child processes of the agent host, communicating with the Python agent layer over stdio JSON-RPC 2.0 [1]. These servers (`kubectl-mcp`, `flux-mcp`, `git-mcp`, and `nixos-mcp`) form the only interface through which agents touch external systems. No Python agent code ever calls `subprocess`, invokes the Kubernetes API directly, or opens a git or SSH connection; all such operations are mediated by a typed MCP tool call that crosses the process boundary.

Each server is started once per FastAPI lifespan via Pydantic AI's `MCPServerStdio` context manager, which spawns the Go binary as a child process and maintains the stdio pipe for the lifetime of the application. The parent Python process and the Go child share no memory; the only communication channel is the JSON-RPC 2.0 message stream over stdin/stdout. This process boundary is the primary trust boundary of the Vigil system: the Python layer expresses intent through typed MCP tool arguments, and the Go layer performs the actual operations against cluster infrastructure, the git remote, and NixOS nodes.

## Why Go and Why MCP-Only

The decision to expose a single MCP-only tool surface is justified in [ADR-0002](../adr/0002-mcp-exclusive-tool-surface.md): typed argument validation prevents injection from string-interpolated shell commands, every mutation is traceable to a named operation in the audit log, and servers can be unit-tested with `io.Pipe()` fake stdio transports without a live cluster.

The choice of Go for all four servers is justified in [ADR-0003](../adr/0003-go-mcp-servers.md): a single static binary requires no runtime on the agent host, the Go standard library provides `crypto/ssh` and `net/http` without external dependencies, and the servers are entirely decoupled from the Python virtualenv. The `mark3labs/mcp-go` SDK [2] provides the stdio server scaffolding and handles MCP protocol framing, tool registration, and JSON-RPC dispatch.

An alternative where the Python agents invoke shell commands via `subprocess`, or call `kubectl` and `ssh` directly, satisfies none of the three requirements: argument arrays constructed at runtime from LLM-generated strings are susceptible to injection; direct subprocess calls produce no structured audit record; and verifying such calls in tests requires either a live cluster or a mock that mirrors the full CLI behaviour of the targeted commands. The Go MCP boundary resolves all three concerns simultaneously, at the cost of a Go toolchain in CI and the modest per-call overhead of JSON-RPC serialization over a local pipe.

Each Go binary is compiled with `go build ./...` into a single statically-linked binary. The deployment unit for each MCP server is a single file placed on the agent host; no shared libraries, no interpreter, no virtualenv are required. The Pydantic AI `MCPServerStdio` context manager locates the binary via a configurable path (passed as an environment variable at orchestrator startup) and exec's it directly. This deployment model means that updating an MCP server is a file copy followed by a process restart: no package manager, no container rebuild, no cluster rolling update.

## Trust Boundary

The stdio pipe between the Python process and each Go child is the trust boundary of the Vigil system. The Python agent layer reasons about what to do; the Go layer controls what can be done. This separation has a concrete security consequence: even if the LLM produces an argument string containing a shell metacharacter, a SQL fragment, or a path traversal sequence, that string reaches the Go server as a typed MCP argument; it is never interpreted by a shell. The Go server validates it against typed parameter declarations before passing it to the underlying API.

The boundary is enforced by process isolation, not by policy. The Python agent has no file descriptor to the Kubernetes API server, no socket to SSH targets, and no reference to the NixOS CLI binaries. The only channel available to the Python layer is the stdin pipe to each Go child, and the only operations that pipe supports are those defined in the MCP tool schema.


## Server Inventory

All four servers implement the MCP specification (revision 2024-11-05) [1] using `mark3labs/mcp-go` [2] at version v0.48.0.

| Server | Language | SDK | go.mod version | Tools |
|--------|----------|-----|----------------|-------|
| kubectl-mcp | Go | mark3labs/mcp-go | v0.48.0 | `get_nodes`, `get_pods`, `describe_pod`, `describe_node`, `get_logs`, `get_events`, `get_taints`, `get_resource_yaml`, `rollout_status`, `delete_resource` |
| flux-mcp | Go | mark3labs/mcp-go | v0.48.0 | `reconcile_kustomization`, `get_kustomization_status`, `get_gitrepository_status` |
| git-mcp | Go | mark3labs/mcp-go | v0.48.0 | `create_branch`, `write_manifest`, `commit_files`, `push_branch`, `create_pr`, `get_pr_status`, `wait_for_gate`, `revert_commit`, `close_pr`, `delete_branch` |
| nixos-mcp | Go | mark3labs/mcp-go | v0.48.0 | `get_generations`, `switch_generation`, `rebuild_test`, `trigger_reconcile`, `get_journal`, `get_systemd_status`, `get_nix_path`, `dry_build`, `etcd_snapshot_save` |

## kubectl-mcp

`kubectl-mcp` exposes read access to the Kubernetes API via the `client-go` library. The read tools (`get_nodes`, `get_pods`, `describe_pod`, `describe_node`, `get_logs`, `get_events`, `get_taints`, `get_resource_yaml`, `rollout_status`) are the Diagnosis agent's primary evidence source and are also used by the Orchestrator pre-checks and the Watchdog. Cluster repairs are performed exclusively through the GitOps path documented in [ADR-0013](../adr/0013-gitops-k8s-remediation.md): the Remediation agent writes manifests via git-mcp and Flux reconciles the merged commit. The only mutating kubectl tool is `delete_resource`, reserved for removing out-of-band live objects that no GitOps commit can address.

Output from every `kubectl-mcp` tool is passed through `truncateOutput` before returning to the agent. The general context limit (4 KB) applies to `describe_pod` and most reads; `get_logs` is capped separately at 2 KB because log streams are typically unbounded. See [Output Truncation](#output-truncation) for the full table and implementation detail.

Authentication to the Kubernetes API is provided by a ServiceAccount kubeconfig. The scope of that ServiceAccount, enforcing least privilege, is the primary K8s-side trust boundary; the MCP server itself makes no additional access decisions beyond what the kubeconfig permits.

## flux-mcp

`flux-mcp` exposes three tools: `reconcile_kustomization`, `get_kustomization_status`, and `get_gitrepository_status`. None of these tools performs a direct cluster mutation. The Orchestrator calls `get_kustomization_status` and `get_gitrepository_status` for the Flux health pre-check before any K8s remediation run; the Remediation agent calls `reconcile_kustomization` at the end of its GitOps sequence to force Flux to pull the merged commit immediately rather than wait for the next reconciliation tick.

Earlier versions of flux-mcp exposed `suspend_kustomization` and `resume_kustomization`, along with a per-resource `guardMutation` middleware that required suspending a Kustomization before any cluster mutation could proceed. The pivot to GitOps remediation makes this guard structurally unnecessary: there is no in-cluster mutation to protect against Flux overwriting, because the agent's repair is a commit on `main` and Flux reconciliation is the application mechanism, not a competing process. The guard was protecting the agent from a problem the agent no longer has.

The K8s remediation round-trip is now `create_branch → write_manifest → commit_files → push_branch → create_pr → wait_for_gate → reconcile_kustomization`. The git-mcp `wait_for_gate` step blocks until the `remediation-gate.yml` workflow has validated and merged the PR (auto-merge is enabled on creation) or rejected it; on success the agent calls `reconcile_kustomization(namespace="flux-system", name="cluster-apps")` to trigger immediate Flux reconciliation against the merged commit. Cluster state converges to the manifest committed on `main` by structural argument: Flux is the only writer to the underlying resources, and the manifest in Git is the only input.

The Orchestrator runs a Flux health pre-check before any K8s remediation: `get_kustomization_status` against `flux-system/cluster-apps` (rejects on `Ready=False`, `Stalled=True`, or `Suspended=true`) and `get_gitrepository_status` against `flux-system/flux-system` (rejects on `Ready=False`). Both checks return `outcome=flux_degraded` and abort the run. The `get_gitrepository_status` check is load-bearing: a broken pull cycle means Flux can still report Kustomization `Ready=True` against a stale commit, but it will not pick up the agent's PR after merge.

On Watchdog-detected regression, the Orchestrator calls `git-mcp.revert_commit(merge_commit_sha)` followed by `flux-mcp.reconcile_kustomization` to force the revert to apply immediately. This makes K8s rollback structurally equivalent to OS rollback (`switch_generation` for NixOS): both undo by reverting to a known-good state declared in version control, not by issuing an imperative restart. ADR-0011 documents the deterministic-Watchdog and the structural symmetry argument in full.

## git-mcp

`git-mcp` exposes ten tools for the GitOps remediation workflow. `create_branch` accepts a `run_id` argument and creates a branch named `remediation/run-<run_id>`; that branch name pattern is exactly what the `remediation-gate.yml` workflow's job-level `if: startsWith(github.head_ref, 'remediation/run-')` condition matches. `write_manifest` overwrites a file at a specified repo-relative path with the provided content. `commit_files` stages and commits the written files. `push_branch` pushes the branch to `origin`. `create_pr` opens a pull request from the branch to `main` and enables auto-merge (squash) via the `gh` CLI. `get_pr_status` returns the current merge or check status of the open PR. `wait_for_gate` blocks until the PR is merged or closed, returning the merge commit SHA on success and an error on CI rejection. `revert_commit` checks out `main` and pushes a revert of the specified merge commit SHA. `close_pr` closes an open PR without merging. `delete_branch` removes the remote branch, cleaning up after a failed gate run.

`git-mcp` is session-scoped per run. `create_branch` clones the repo into a fresh temporary directory and stores the clone path in process-local memory; subsequent calls (`write_manifest`, `commit_files`, `push_branch`) operate within that session directory. Cloning happens once per `create_branch` invocation; no persistent global clone is kept across runs. If the agent process restarts between calls, the session state is lost and the run must start a new session from `create_branch`.

`create_pr` enables auto-merge (squash) on the PR via the `gh` CLI immediately after creation. The `remediation-gate.yml` workflow carries no `pull-requests: write` permission and does not call `gh pr merge` itself — the auto-merge flag is honoured by GitHub once the required status checks pass. `wait_for_gate` polls the PR status until merged or closed; on merge it returns `gate passed: merged sha=<sha>`; on close-without-merge it returns an error that the Remediation agent handles by calling `close_pr` + `delete_branch` to leave the repo in a clean state.

`revert_commit` checks out `main` in the existing session clone, runs `git revert --no-edit <merge_sha>`, and pushes the result to `origin/main` directly. The Orchestrator immediately calls `flux-mcp.reconcile_kustomization` after the revert push to force Flux to pull the reverted state without waiting for the next reconciliation tick. `close_pr` and `delete_branch` — used on gate failure only — keep the repo state clean across eval campaigns by ensuring no orphan open PRs accumulate between runs.

## nixos-mcp

`nixos-mcp` exposes `get_generations`, `switch_generation`, `rebuild_test`, `trigger_reconcile`, `get_journal`, `get_systemd_status`, `get_nix_path`, `dry_build`, and `etcd_snapshot_save`. All operations are executed over an SSH connection to the target NixOS node, with the `host` parameter (propagated from the Diagnosis agent's `target_host` field in `DiagnosisReport`) determining which node receives each command.

The NixOS remediation path follows a staged protocol designed around the NixOS generations model. `rebuild_test` activates the current NixOS configuration in a trial mode (equivalent to `nixos-rebuild test` on the node) and returns the rebuild exit code alongside the systemd health gate status. If the health gate indicates a passing state, the trial activation stands and the agent can exit the OS remediation path. If the health gate fails or the rebuild exits non-zero, `get_generations` retrieves the available generation list and `switch_generation` rolls the node back to a prior generation. `switch_generation` is the primary OS remediation verb validated during evaluation: agents reliably converge on generation switching when `rebuild_test` indicates a health-gate failure, making it the correct verb to invoke rather than repeated rebuild attempts.

`etcd_snapshot_save` triggers a snapshot of the etcd cluster state to a specified destination path before any OS-level mutation, providing a recovery point for the control plane data. `get_journal` retrieves systemd journal entries for a named unit, and `get_systemd_status` returns the `systemctl status` output for a unit; both are read-only tools used during OS-layer diagnosis by the Diagnosis agent.

All nixos-mcp operations are filtered through `truncateOutput` at the same byte limits as the other servers. This is particularly relevant for `get_journal`, which can return thousands of lines for a unit that has been cycling, and for `get_generations`, whose output grows with the number of stored NixOS generations on the node.

The dead-man's switch design (the NixOS timer module that forces a revert if the health gate does not pass within its calibrated window) is the safety net that operates independently of the agent. That mechanism is covered in [gitops-nixos.md](gitops-nixos.md); `nixos-mcp` is the agent-facing interface layer above it.

The read-only/write distinction within nixos-mcp mirrors the pattern in kubectl-mcp. `get_journal`, `get_systemd_status`, and `get_generations` are pure reads that the Diagnosis agent can call without risk of mutation. `switch_generation` and `etcd_snapshot_save` are excluded from the Diagnosis agent's `FilteredToolset` to prevent premature OS mutations before a `DiagnosisReport` is returned. `rebuild_test` is accessible to the Diagnosis agent: it is a read-like probe that activates a trial configuration without committing it, and is therefore not excluded from the diagnostic phase.

| Tool | Read / Write | Diagnosis | Remediation | Purpose |
|------|-------------|-----------|-------------|---------|
| `get_journal` | Read | ✓ | ✓ | Fetch systemd journal for a unit on the target node |
| `get_systemd_status` | Read | ✓ | ✓ | Return `systemctl status` for a unit |
| `get_generations` | Read | ✓ | ✓ | List stored NixOS generations and their activation timestamps |
| `rebuild_test` | Read-like | ✓ | ✓ | Trial-activate current config; does not commit if health gate fails |
| `switch_generation` | Write | ✗ | ✓ | Activate a prior NixOS generation; primary OS remediation verb |
| `etcd_snapshot_save` | Write | ✗ | ✓ | Snapshot etcd state before a destructive OS change |

`switch_generation` is the primary OS remediation verb validated across the OS and cross-layer eval scenarios. `etcd_snapshot_save` is called as a safety step before any generation switch that crosses a major NixOS configuration boundary, giving the Orchestrator a restore point independent of the NixOS generation list.

The `rebuild_test` tool is the only nixos-mcp tool classified as read-like rather than write. It invokes `nixos-rebuild test` on the target host, which activates the current configuration in memory without writing a new bootloader entry; if the health gate fails, the dead-man's switch timer reverts the node automatically without agent intervention.

## Output Truncation

Every tool in all four MCP servers passes its string output through `truncateOutput` before returning a `CallToolResult`. The motivation is context-window protection: unrestricted log output or `kubectl describe` dumps can easily exceed the token budget of the downstream LLM, corrupting the agent's working context or triggering a request failure due to token limits.

The byte limits are defined as named constants in each server's `internal/config/config.go` and are overridable via environment variables at server startup:

| Context | Constant | Default |
|---------|----------|---------|
| Describe / general | `MaxOutputBytesDescribe` | 4096 bytes (4 KB) |
| Logs | `MaxOutputBytesLogs` | 2048 bytes (2 KB) |
| Prometheus | `MaxOutputBytesPrometheus` | 10240 bytes (10 KB) |

The implementation in `mcp-servers/kubectl-mcp/internal/k8s/truncate.go`:

```go
// mcp-servers/kubectl-mcp/internal/k8s/truncate.go
func truncateOutput(s string, maxBytes int) string {
    if len(s) <= maxBytes {
        return s
    }
    clipped := s[:maxBytes]
    clippedLines := strings.Split(clipped, "\n")
    totalLines := len(strings.Split(s, "\n"))
    omitted := totalLines - len(clippedLines)
    return strings.Join(clippedLines, "\n") + fmt.Sprintf("\n[TRUNCATED: %d lines omitted]", omitted)
}
```

The function clips the output at the byte boundary first, then counts the omitted lines relative to the total line count of the original string. The resulting suffix `[TRUNCATED: N lines omitted]` serves a specific purpose for downstream agent reasoning: it tells the LLM that the output was clipped and quantifies the omission, preventing silent truncation from causing the agent to treat a partial resource description as complete. Without this suffix, an agent receiving a clipped `kubectl describe` output has no mechanism to distinguish a full response from one that was cut off mid-field.

The same `truncateOutput` function (or a local equivalent) is used by `flux-mcp`, `git-mcp`, and `nixos-mcp` for their respective output contexts. The Prometheus byte limit (10 KB) is higher than the general limit because Prometheus metric dumps are expected to be larger and are consumed by the Orchestrator's polling path rather than fed directly into the agent's reasoning context.

## Server Lifecycle

All four servers are started once during the FastAPI application lifespan and remain running for the duration of the process. The boot-once pattern is critical: starting a new MCP server subprocess per agent request would incur the full Go binary startup cost on each call, and more importantly would lose any per-session state in git-mcp (the session clone directory path). By keeping the servers alive for the full lifespan, the session state persists across all tool calls within a single Orchestrator run.

The Pydantic AI `MCPServerStdio` context manager handles the subprocess lifecycle: on entry it spawns the Go binary and performs the MCP `initialize` handshake; on exit it sends a termination signal and waits for the child to exit cleanly. If the Go server crashes during a run, `MCPServerStdio` surfaces the error as a tool call failure, which the circuit breaker counts as a consecutive error toward the trip threshold.

The four servers are independent processes with no shared state. The only coordination between servers happens at the Python layer, where the Remediation agent sequences tool calls across servers in a defined order (git operations via git-mcp, then Flux reconciliation via flux-mcp).

Error handling follows a consistent pattern across all four servers: when an operation against an external system fails, the handler returns a `mcp.NewToolResultError(...)` rather than an error return value. The MCP specification [1] distinguishes tool errors (failures within the tool's domain, reported as `isError: true` in the result) from protocol errors (failures in the JSON-RPC transport itself). Vigil uses tool errors for all cluster-side failures (Kubernetes API errors, git push failures, NixOS rebuild failures) so that the LLM receives a structured description of what went wrong rather than an opaque transport failure. The circuit breaker in the Orchestrator counts consecutive tool errors (not transport errors) toward the trip threshold.

## Testing Strategy

Each MCP server has a Go unit test suite that runs entirely without a live cluster. The stdio transport layer is replaced with `io.Pipe()` fakes: one end of the pipe drives the MCP JSON-RPC protocol as a test client, the other end runs the real server handler under test. This approach verifies that JSON-RPC framing, argument parsing, typed argument validation, and error handling all behave correctly without any network dependency.

The `truncateOutput` byte limits are tested with strings that are exactly at the limit, one byte over, and significantly over. The git-mcp session model is tested with fake git clients that return deterministic responses, verifying that `create_branch` initialises the session and that subsequent calls within the same session use the stored clone path.

Integration tests run against the local K3s homelab cluster and exercise the full call path including the Kubernetes API via `client-go`, the Flux REST API, and the SSH connection to a real node. These tests are not required to pass in CI environments without cluster access; the unit-test suite is the CI gate.

The CI pipeline runs two independent lint and test stages: `ruff` and `pytest` for the Python agent layer, and `golangci-lint` plus `go test ./...` for the four Go MCP servers. The Go test stage covers all four servers and runs without cluster access, relying entirely on the `io.Pipe()` fake transport. A test that requires a live cluster is a test that cannot run in CI; this constraint is by design and is enforced by the test suite structure, not by convention.

The `io.Pipe()` approach also validates a property that cannot be tested against a real cluster: the JSON-RPC framing itself. A real cluster call succeeds or fails based on cluster state, not on whether the MCP message was correctly serialised. The fake transport lets the test assert on the exact bytes exchanged, catching protocol-level regressions in tool definitions, argument schemas, and result encoding that would be invisible in a live integration test.

## Related Documents

- [ADR-0002](../adr/0002-mcp-exclusive-tool-surface.md) — decision record for the MCP-only tool surface, including the alternatives considered and their failure modes in the Vigil context
- [ADR-0003](../adr/0003-go-mcp-servers.md) — decision record for Go as the MCP server implementation language
- `docs/architecture/overview.md` — system topology, showing how the four MCP servers fit within the full component graph including the Python agent layer, K8s cluster, and Flux GitOps controller
- `docs/architecture/agent-design.md` — agent responsibilities and the sequential K8s remediation sequencing (git-mcp GitOps sequence, then Watchdog) and the concurrent OS remediation pattern

## References

[1] Anthropic, "Model Context Protocol Specification," revision 2024-11-05. Available: https://spec.modelcontextprotocol.io/specification/2024-11-05/

[2] mark3labs, "mcp-go: A Go implementation of the Model Context Protocol (MCP)," v0.48.0. Available: https://github.com/mark3labs/mcp-go
