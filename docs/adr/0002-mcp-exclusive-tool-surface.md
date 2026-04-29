# ADR-0002: MCP as exclusive agent tool surface

**Status**: Accepted

## Context

Agents must read and mutate Kubernetes resources, execute SSH commands on cluster nodes, and modify NixOS configuration. Three concerns shape the tool surface design:

1. **Safety**: Raw subprocess calls with string-interpolated arguments introduce command injection risk
2. **Auditability**: Every mutation should be traceable to a named, typed operation
3. **Testability**: Tool servers should be verifiable in isolation, without a live cluster

An approach where agents invoke `kubectl`, `ssh`, and `nixos-rebuild` directly via subprocess satisfies none of these.

## Decision

All agent actions flow exclusively through typed MCP (Model Context Protocol) tool calls. Agents never invoke `subprocess`, `os.system`, or shell commands directly. Four Go MCP servers expose typed tools: `kubectl-mcp`, `flux-mcp`, `ssh-mcp`, and `nixos-mcp`.

## Consequences

- Typed tool inputs enforce argument validation before any cluster mutation reaches the wire
- Every tool call is logged with its arguments, enabling a complete audit trail
- MCP servers can be unit-tested with fake stdio pipes without a live cluster
- The stdio transport adds modest per-call latency compared to a direct in-process API call
- Adding a new capability requires a new typed tool definition in Go, not just a new subprocess invocation
