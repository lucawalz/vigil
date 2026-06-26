---
status: Accepted
date: 2026-04-15
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0003: Go for MCP server implementations

## Context and Problem Statement

MCP servers run as long-lived child processes on the agent host, communicating over stdio. Requirements:

- Compile to a single static binary for deployment without a runtime environment
- Call the Kubernetes API (`client-go`), Flux REST API, `crypto/ssh`, and NixOS CLI tools
- Impose no runtime dependency on the Python agent environment

Python MCP servers would share the agent virtualenv but would add import latency and complicate dependency isolation. Shell-script servers are impractical for the SSH and Kubernetes use cases.

The agent host environment runs Python via `uv` with a pinned virtualenv. Any MCP server sharing that environment creates a coupling: a dependency update in the agent project can break the server, and the server cannot be rebuilt or updated independently. A language choice that produces standalone executables severs this coupling entirely.

## Decision Drivers

- Single static binary deploys without a runtime; `go build ./...` is the complete build step
- `client-go` provides typed, authenticated Kubernetes API access without shelling out to `kubectl`
- `crypto/ssh` provides SSH transport without requiring an OpenSSH installation on the agent host
- The `mcptest` in-process server enables unit testing of the full MCP server without a live cluster
- Decoupling from the Python runtime prevents MCP server breakage from Python dependency churn
- The `mcp-go` SDK (mark3labs/mcp-go v0.55.0) implements the MCP JSON-RPC protocol in Go

## Considered Options

- Go
- Python MCP servers
- Shell-script servers

## Decision Outcome

Chosen option: "Go", because it produces standalone binaries decoupled from the Python runtime, provides native access to `client-go` and `crypto/ssh` without subprocess wrapping, and supports `mcptest` in-process unit testing without a live cluster.

### Consequences

- Good: Each server compiles to a single statically linked binary; deployment is `go build ./...`
- Good: Go's stdlib provides `crypto/ssh` (no OpenSSH runtime required) and `net/http` for the Flux API
- Good: Servers are completely decoupled from the Python runtime and can be rebuilt independently
- Bad: The monorepo requires a Go toolchain alongside Python and uv, increasing the onboarding surface
- Bad: CI runs two separate lint and test pipelines: ruff + pytest for Python, golangci-lint + go test for Go

**Validation Status:** Verified. 4/4 MCP servers; clean interface-driven pattern; `mcptest` tests reliable across the v1.0 Hetzner eval campaign.

**Update 2026-06-27:** The `nixos-mcp` SSH client now rides out transient node-unreachable windows. A NixOS generation switch briefly drops a node's SSH daemon for seconds, and the single-attempt dial aborted any eval call landing in that window. The TCP dial is wrapped in a bounded retry-with-backoff loop that retries only transient transport errors (`net.Error` timeouts plus connection refused/reset); deterministic failures (host allow-list, command validation, authentication, session, and command errors) fail fast with no retry. The total retry budget stays well under the 60-second MCP call timeout. Two knobs tune the behaviour: `SSH_DIAL_RETRIES` (default 3) caps the attempt count and `SSH_DIAL_BACKOFF_MS` (default 500) sets the initial exponential backoff. The change uses only the Go standard library, so no module dependency or vendor hash is affected.

### Confirmation

The decision holds as long as:
- All four MCP servers (`kubectl-mcp`, `flux-mcp`, `git-mcp`, `nixos-mcp`) build with `go build ./...` to single static binaries; the original `ssh-mcp` server was removed once OS remediation moved to the GitOps and NixOS-generation path
- Each server has a passing Go test suite using the `mcptest` in-process transport without a live cluster
- No MCP server imports from the Python agent packages or depends on the `uv` virtualenv

### Pros and Cons of the Options

#### Go

- Good: `go build ./...` produces standalone executables with no runtime dependency
- Good: `client-go` provides typed, authenticated K8s API access; `crypto/ssh` provides SSH without OpenSSH
- Good: Interface-driven design enables `mcptest` in-process unit testing of the full JSON-RPC handler chain
- Bad: Requires a Go toolchain in CI and on developer machines alongside the Python/uv stack

#### Python MCP servers

- Good: No additional language toolchain; shares the existing `uv` workspace
- Bad: Python MCP servers would share the agent virtualenv, coupling MCP server lifecycle to Python interpreter and dependency management. Each new MCP server bump would force a Pydantic-AI compatibility check; a `pip install` regression in the agent project would silently break the MCP layer. Go binaries are wholly decoupled from the Python runtime; `go build ./...` produces standalone executables.

#### Shell-script servers

- Good: Zero build step; scripts are editable without recompilation
- Bad: Shell scripts cannot reasonably implement the MCP JSON-RPC protocol or call `client-go`/Flux REST APIs without spawning sub-processes per call, multiplying the command-injection surface they were meant to avoid. The kubectl-mcp tool list (`get_pods`, `describe_pod`, `get_logs`, `delete_resource`) requires structured K8s API access, not text-pasting through `kubectl`.

## More Information

- MCP-only tool surface decision: [`0002-mcp-exclusive-tool-surface.md`](0002-mcp-exclusive-tool-surface.md)
