# ADR-0003: Go for MCP server implementations

**Status**: Accepted

## Context

MCP servers run as long-lived child processes on the agent host, communicating over stdio. Requirements:

- Compile to a single static binary for deployment without a runtime environment
- Call the Kubernetes API (`client-go`), Flux REST API, `crypto/ssh`, and NixOS CLI tools
- Impose no runtime dependency on the Python agent environment

Python MCP servers would share the agent virtualenv but would add import latency and complicate dependency isolation. Shell-script servers are impractical for the SSH and Kubernetes use cases.

## Decision

Implement all four MCP servers (`kubectl-mcp`, `flux-mcp`, `ssh-mcp`, `nixos-mcp`) in Go, using the [mcp-go](https://github.com/mark3labs/mcp-go) SDK.

## Consequences

- Each server compiles to a single statically linked binary; deployment is `go build ./...`
- Go's stdlib provides `crypto/ssh` (no OpenSSH runtime required) and `net/http` for the Flux API
- Servers are completely decoupled from the Python runtime and can be rebuilt independently
- The monorepo requires a Go toolchain alongside Python and uv, increasing the onboarding surface
- CI runs two separate lint and test pipelines: ruff + pytest for Python, golangci-lint + go test for Go
