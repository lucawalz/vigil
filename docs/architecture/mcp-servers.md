# Vigil — MCP Servers

Four Go MCP servers run as long-lived child processes of the agent host, communicating with the Python agent layer over stdio JSON-RPC 2.0 [1]. These servers (`kubectl-mcp`, `flux-mcp`, `ssh-mcp`, and `nixos-mcp`) form the only interface through which agents touch external systems. No Python agent code ever calls `subprocess`, invokes the Kubernetes API directly, or opens an SSH connection; all such operations are mediated by a typed MCP tool call that crosses the process boundary.

Each server is started once per FastAPI lifespan via Pydantic AI's `MCPServerStdio` context manager, which spawns the Go binary as a child process and maintains the stdio pipe for the lifetime of the application. The parent Python process and the Go child share no memory; the only communication channel is the JSON-RPC 2.0 message stream over stdin/stdout. This process boundary is the primary trust boundary of the Vigil system: the Python layer expresses intent through typed MCP tool arguments, and the Go layer performs the actual operations against cluster infrastructure, SSH targets, and NixOS nodes.

## Why Go and Why MCP-Only

The decision to expose a single MCP-only tool surface is justified in [ADR-0002](../adr/0002-mcp-exclusive-tool-surface.md): typed argument validation prevents injection from string-interpolated shell commands, every mutation is traceable to a named operation in the audit log, and servers can be unit-tested with `io.Pipe()` fake stdio transports without a live cluster.

The choice of Go for all four servers is justified in [ADR-0003](../adr/0003-go-mcp-servers.md): a single static binary requires no runtime on the agent host, the Go standard library provides `crypto/ssh` and `net/http` without external dependencies, and the servers are entirely decoupled from the Python virtualenv. The `mark3labs/mcp-go` SDK [2] provides the stdio server scaffolding and handles MCP protocol framing, tool registration, and JSON-RPC dispatch.

An alternative where the Python agents invoke shell commands via `subprocess`, or call `kubectl` and `ssh` directly, satisfies none of the three requirements: argument arrays constructed at runtime from LLM-generated strings are susceptible to injection; direct subprocess calls produce no structured audit record; and verifying such calls in tests requires either a live cluster or a mock that mirrors the full CLI behaviour of the targeted commands. The Go MCP boundary resolves all three concerns simultaneously, at the cost of a Go toolchain in CI and the modest per-call overhead of JSON-RPC serialization over a local pipe.

Each Go binary is compiled with `go build ./...` into a single statically-linked binary. The deployment unit for each MCP server is a single file placed on the agent host; no shared libraries, no interpreter, no virtualenv are required. The Pydantic AI `MCPServerStdio` context manager locates the binary via a configurable path (passed as an environment variable at orchestrator startup) and exec's it directly. This deployment model means that updating an MCP server is a file copy followed by a process restart: no package manager, no container rebuild, no cluster rolling update.

## Trust Boundary

The stdio pipe between the Python process and each Go child is the trust boundary of the Vigil system. The Python agent layer reasons about what to do; the Go layer controls what can be done. This separation has a concrete security consequence: even if the LLM produces an argument string containing a shell metacharacter, a SQL fragment, or a path traversal sequence, that string reaches the Go server as a typed MCP argument; it is never interpreted by a shell. The Go server validates it against typed parameter declarations and, where applicable, against the allowlist or the guardMutation state before passing it to the underlying API.

The boundary is enforced by process isolation, not by policy. The Python agent has no file descriptor to the Kubernetes API server, no socket to SSH targets, and no reference to the NixOS CLI binaries. The only channel available to the Python layer is the stdin pipe to each Go child, and the only operations that pipe supports are those defined in the MCP tool schema.


## Server Inventory

All four servers implement the MCP specification (revision 2024-11-05) [1] using `mark3labs/mcp-go` [2] at version v0.48.0.

| Server | Language | SDK | go.mod version | Tools |
|--------|----------|-----|----------------|-------|
| kubectl-mcp | Go | mark3labs/mcp-go | v0.48.0 | `get_nodes`, `get_pods`, `describe_pod`, `get_logs`, `rollout_undo`, `apply_patch`, `rollout_status` |
| flux-mcp | Go | mark3labs/mcp-go | v0.48.0 | `suspend_kustomization`, `resume_kustomization`, `reconcile_kustomization`, `get_kustomization_status` |
| ssh-mcp | Go | mark3labs/mcp-go | v0.48.0 | `run_allowed_command` (with static allowlist) |
| nixos-mcp | Go | mark3labs/mcp-go | v0.48.0 | `get_generations`, `switch_generation`, `rebuild_test`, `get_journal`, `get_systemd_status`, `etcd_snapshot_save` |

## kubectl-mcp

`kubectl-mcp` exposes both read and write access to the Kubernetes API via the `client-go` library. The read tools (`get_nodes`, `get_pods`, `describe_pod`, `get_logs`, `rollout_status`) are available to both the Diagnosis and Remediation agents. The write tools (`apply_patch` and `rollout_undo`) are excluded from the Diagnosis agent's tool scope via `FilteredToolset`, ensuring that the diagnostic phase can observe cluster state without risking inadvertent mutation.

`apply_patch` performs a strategic-merge or server-side apply patch against a named Kubernetes resource; it is the primary K8s remediation verb for workload-level faults such as adjusting resource requests, correcting image tags, or restoring a misconfigured ConfigMap. `rollout_undo` triggers a rollback of a Deployment or DaemonSet to its previous revision; it is invoked by the Orchestrator (not the Remediation agent) when the Watchdog reports `WatchdogResult.degraded=True` after a remediation attempt, signalling that the repair itself caused regression.

Output from every `kubectl-mcp` tool is passed through `truncateOutput` before returning to the agent. The general context limit (4 KB) applies to `describe_pod` and most reads; `get_logs` is capped separately at 2 KB because log streams are typically unbounded. See [Output Truncation](#output-truncation) for the full table and implementation detail.

Authentication to the Kubernetes API is provided by a ServiceAccount kubeconfig. The scope of that ServiceAccount, enforcing least privilege, is the primary K8s-side trust boundary; the MCP server itself makes no additional access decisions beyond what the kubeconfig permits.

## flux-mcp and the guardMutation Correctness Argument

`flux-mcp` exposes four tools for controlling Flux Kustomization resources: `suspend_kustomization`, `resume_kustomization`, `reconcile_kustomization`, and `get_kustomization_status`. Two of the four are guarded by a middleware called `guardMutation`. Understanding why this guard exists is central to understanding the correctness model of the K8s remediation path.

When Flux is active, it continuously reconciles Kustomization resources against the desired state in Git. If an agent patches a Kubernetes resource while the corresponding Kustomization is reconciling, Flux will overwrite the agent's patch on its next reconciliation cycle, silently undoing the repair. This is not a rare edge case; Flux's default reconciliation interval is short enough that mid-remediation overwrites occur in practice. The fix applied by the agent disappears, and subsequent health checks reflect the reverted state rather than the agent's intervention.

The `guardMutation` middleware enforces a mandatory protocol at the Go layer: a Kustomization must be suspended before any mutating tool call can proceed for that resource. This is not a naming convention or a prompt instruction to the LLM; it is a hard Go-layer check that the named resource was previously registered in the suspended set. The enforcement mechanism is a `suspendedNames map[string]bool` protected by a `sync.Mutex` inside the `FluxServer` struct:

```go
// mcp-servers/flux-mcp/internal/server/server.go
func (s *FluxServer) guardMutation(next server.ToolHandlerFunc) server.ToolHandlerFunc {
    return func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
        name, _ := req.GetArguments()["name"].(string)
        s.mu.Lock()
        allowed := name != "" && s.suspendedNames[name]
        s.mu.Unlock()
        if !allowed {
            return mcp.NewToolResultError(
                "flux_suspended guard: call suspend_kustomization for this resource before any mutating tool",
            ), nil
        }
        return next(ctx, req)
    }
}
```

The guard is wrapped around `resume_kustomization` and `reconcile_kustomization`. It is deliberately absent from `suspend_kustomization`, which is the gate enabler: calling `suspend_kustomization(name="apps")` registers `"apps"` in `suspendedNames` and simultaneously suspends the Kustomization in the Flux API, halting further reconciliation for that resource.

The call sequence for a correct K8s remediation round-trip is therefore:

1. `suspend_kustomization(name="apps")` — registers `"apps"` in `suspendedNames`; Flux stops reconciling `apps`
2. `apply_patch(...)` or `rollout_undo(...)` (kubectl-mcp) — the repair action; Flux is suspended so it will not overwrite the change
3. `resume_kustomization(name="apps")` — removes `"apps"` from `suspendedNames`; Flux resumes reconciliation

`reconcile_kustomization` is also gated by `guardMutation` (it requires prior suspension) and may be called between steps 2 and 3 to force an immediate Flux re-sync, but it is not the repair verb.

If the agent attempts `reconcile_kustomization(name="infra")` without first suspending `"infra"`, the guard rejects the call immediately with a `ToolResultError` containing the message shown in the excerpt above. The state is per-session (process lifetime) and per-resource: suspending `"apps"` does not permit mutations on `"infra"`, and restarting the agent process clears all suspend state because `suspendedNames` is an in-memory map with no persistence.

The `resume_kustomization` step is also gated by `guardMutation`. This prevents a double-resume (calling resume on a resource that was never suspended in this session), which would produce a confusing Flux API error rather than a clear guard rejection. The `onResume` callback deletes the name from the set; a subsequent resume attempt for the same name will find the guard empty and return an error before any Flux API call is made.

The locking discipline is intentional: `name != ""` is checked inside the lock to avoid a race between a concurrent `onSuspend` callback and the guard read. The `sync.Mutex` is the only synchronisation primitive; no channel or condition variable is needed because the guard is a single boolean map lookup.

## ssh-mcp and the Allowlist

`ssh-mcp` exposes a single tool: `run_allowed_command`. The tool accepts a binary name and an argument list, validates both against a static allowlist, and executes via `exec.Command(binary, args...)` over an SSH connection to the target node using Go's `crypto/ssh` library. No shell is involved at any point in the execution path.

The static allowlist enforced in `validateCommand` is:

```
journalctl: (any args)
systemctl:  status, is-active, is-failed, stop, start
free, df, uptime, ss: (any args)
ip: addr, route, link
fallocate: (any args)
nixos-rebuild: switch
```

Validation is two-stage. Shell metacharacters (``[;&|$`(){}<>\n\r]``) are rejected before the allowlist lookup: any argument matching that character class causes `validateCommand` to return an error immediately, regardless of which binary was requested. Only after the metacharacter check passes does the allowlist lookup proceed. For binaries with a restricted sub-command set (`systemctl` and `ip`), the first argument is checked against the permitted sub-command list. Execution uses `exec.Command(binary, args...)` directly: the argument list is passed as a slice to the OS, bypassing any shell, and no shell expansion or globbing occurs.

The vigil-agent process runs as a non-root user on the agent host. Privilege escalation for operations such as `nixos-rebuild switch` must come from the allowed commands themselves via explicit `sudo` configuration on the target node, not from shell expansion. The allowlist is the boundary between what the Remediation agent can request and what can reach the node's operating system.

The SSH connection to each target node is established using Go's `crypto/ssh` standard library package, which provides a pure-Go SSH client without a dependency on the system OpenSSH installation. SSH credentials are supplied at server startup via environment variables and held for the lifetime of the process; connections are established per-call rather than pooled, so a transient SSH failure affects only the in-flight call and does not corrupt shared connection state. The `target` parameter on each `run_allowed_command` call specifies which cluster node receives the command, allowing the single `ssh-mcp` instance to reach any node the agent host has SSH access to.

## nixos-mcp

`nixos-mcp` exposes six tools: `get_generations`, `switch_generation`, `rebuild_test`, `get_journal`, `get_systemd_status`, and `etcd_snapshot_save`. All six operations are executed over an SSH connection to the target NixOS node, with the `host` parameter (propagated from the Diagnosis agent's `target_host` field in `DiagnosisReport`) determining which node receives each command.

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

The same `truncateOutput` function (or a local equivalent) is used by `flux-mcp`, `ssh-mcp`, and `nixos-mcp` for their respective output contexts. The Prometheus byte limit (10 KB) is higher than the general limit because Prometheus metric dumps are expected to be larger and are consumed by the Orchestrator's polling path rather than fed directly into the agent's reasoning context.

## Server Lifecycle

All four servers are started once during the FastAPI application lifespan and remain running for the duration of the process. The boot-once pattern is critical: starting a new MCP server subprocess per agent request would incur the full Go binary startup cost on each call, and more importantly would lose any per-session state, including the `suspendedNames` set in `flux-mcp`. By keeping the servers alive for the full lifespan, the `suspendedNames` map persists across all tool calls within a single Orchestrator run.

The Pydantic AI `MCPServerStdio` context manager handles the subprocess lifecycle: on entry it spawns the Go binary and performs the MCP `initialize` handshake; on exit it sends a termination signal and waits for the child to exit cleanly. If the Go server crashes during a run, `MCPServerStdio` surfaces the error as a tool call failure, which the circuit breaker counts as a consecutive error toward the trip threshold.

The four servers are independent processes with no shared state. `flux-mcp`'s `suspendedNames` map is not visible to `kubectl-mcp` or any other server. The only coordination between servers happens at the Python layer, where the Remediation agent sequences tool calls across servers in a defined order (suspend via flux-mcp, then patch via kubectl-mcp, then resume via flux-mcp).

Error handling follows a consistent pattern across all four servers: when an operation against an external system fails, the handler returns a `mcp.NewToolResultError(...)` rather than an error return value. The MCP specification [1] distinguishes tool errors (failures within the tool's domain, reported as `isError: true` in the result) from protocol errors (failures in the JSON-RPC transport itself). Vigil uses tool errors for all cluster-side failures (Kubernetes API errors, SSH connection failures, NixOS rebuild failures) so that the LLM receives a structured description of what went wrong rather than an opaque transport failure. The circuit breaker in the Orchestrator counts consecutive tool errors (not transport errors) toward the trip threshold.

## Testing Strategy

Each MCP server has a Go unit test suite that runs entirely without a live cluster. The stdio transport layer is replaced with `io.Pipe()` fakes: one end of the pipe drives the MCP JSON-RPC protocol as a test client, the other end runs the real server handler under test. This approach verifies that JSON-RPC framing, argument parsing, typed argument validation, and error handling all behave correctly without any network dependency.

The `guardMutation` state transitions are tested by calling `suspend_kustomization` and then verifying that subsequent calls to `reconcile_kustomization` and `resume_kustomization` succeed or fail as expected depending on the resource name supplied. The `validateCommand` allowlist logic is tested with both permitted and forbidden binaries, permitted and forbidden sub-commands, and arguments containing shell metacharacters. The `truncateOutput` byte limits are tested with strings that are exactly at the limit, one byte over, and significantly over.

Integration tests run against the local K3s homelab cluster and exercise the full call path including the Kubernetes API via `client-go`, the Flux REST API, and the SSH connection to a real node. These tests are not required to pass in CI environments without cluster access; the unit-test suite is the CI gate.

The CI pipeline runs two independent lint and test stages: `ruff` and `pytest` for the Python agent layer, and `golangci-lint` plus `go test ./...` for the four Go MCP servers. The Go test stage covers all four servers and runs without cluster access, relying entirely on the `io.Pipe()` fake transport. A test that requires a live cluster is a test that cannot run in CI; this constraint is by design and is enforced by the test suite structure, not by convention.

The `io.Pipe()` approach also validates a property that cannot be tested against a real cluster: the JSON-RPC framing itself. A real cluster call succeeds or fails based on cluster state, not on whether the MCP message was correctly serialised. The fake transport lets the test assert on the exact bytes exchanged, catching protocol-level regressions in tool definitions, argument schemas, and result encoding that would be invisible in a live integration test.

## Related Documents

- [ADR-0002](../adr/0002-mcp-exclusive-tool-surface.md) — decision record for the MCP-only tool surface, including the alternatives considered and their failure modes in the Vigil context
- [ADR-0003](../adr/0003-go-mcp-servers.md) — decision record for Go as the MCP server implementation language
- `docs/architecture/overview.md` — system topology, showing how the four MCP servers fit within the full component graph including the Python agent layer, K8s cluster, and Flux GitOps controller
- `docs/architecture/agent-design.md` — agent responsibilities and the asyncio.TaskGroup remediation+watchdog parallel pattern that sequences calls across kubectl-mcp and flux-mcp

## References

[1] Anthropic, "Model Context Protocol Specification," revision 2024-11-05. Available: https://spec.modelcontextprotocol.io/specification/2024-11-05/

[2] mark3labs, "mcp-go: A Go implementation of the Model Context Protocol (MCP)," v0.48.0. Available: https://github.com/mark3labs/mcp-go
