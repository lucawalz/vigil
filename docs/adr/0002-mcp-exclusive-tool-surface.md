---
status: Accepted
date: 2026-04-14
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0002: MCP as exclusive agent tool surface

## Context and Problem Statement

Agents must read and mutate Kubernetes resources, execute SSH commands on cluster nodes, and modify NixOS configuration. Three concerns shape the tool surface design:

1. **Safety**: Raw subprocess calls with string-interpolated arguments introduce command injection risk
2. **Auditability**: Every mutation should be traceable to a named, typed operation
3. **Testability**: Tool servers should be verifiable in isolation, without a live cluster

An approach where agents invoke `kubectl`, `ssh`, and `nixos-rebuild` directly via subprocess satisfies none of these. Vigil's eval scenarios include adversarial pod names and StatefulSet selectors; any string-interpolation path is a structural injection risk, not merely a theoretical one.

## Decision Drivers

- Command injection must be structurally impossible, not a matter of careful quoting
- Every tool call must carry a typed argument record for audit trail purposes
- MCP servers must be unit-testable without a live cluster (via `io.Pipe()` fakes in Go)
- The tool surface must be extensible: new capabilities should require a new typed tool definition, not a new subprocess invocation
- The stdio transport boundary isolates Python agent code from direct cluster API access

## Considered Options

- MCP-only tool surface
- Direct subprocess from agents
- Thin shell-script wrappers

## Decision Outcome

Chosen option: "MCP-only tool surface", because it makes command injection structurally impossible at the typed-argument boundary, makes every tool call auditable, and enables isolation testing of each server with `io.Pipe()` fakes without a live cluster.

### Consequences

- Good: Typed tool inputs enforce argument validation before any cluster mutation reaches the wire
- Good: Every tool call is logged with its arguments, enabling a complete audit trail
- Good: MCP servers can be unit-tested with fake stdio pipes without a live cluster
- Bad: The stdio transport adds modest per-call latency compared to a direct in-process API call
- Bad: Adding a new capability requires a new typed tool definition in Go, not just a new subprocess invocation

**Validation Status:** Verified — 4/4 MCP servers tested with `io.Pipe()` fakes; no regressions across the v1.0 Hetzner eval campaign.

### Confirmation

The decision holds as long as:
- No agent module contains a direct call to `subprocess`, `os.system`, or any shell invocation
- All cluster mutations are routed through one of the four typed MCP servers (`kubectl-mcp`, `flux-mcp`, `git-mcp`, `nixos-mcp`); the original `ssh-mcp` server was removed once OS remediation moved to the GitOps and NixOS-generation path, leaving no separate command-execution surface
- Each MCP server maintains a passing test suite using `io.Pipe()` fake transport without requiring a live cluster

### Pros and Cons of the Options

#### MCP-only tool surface

- Good: JSON-RPC typed arguments cross the wire as structured data; shell metacharacters are irrelevant at the Python layer
- Good: `io.Pipe()` fake transport enables full server testing without a live Kubernetes cluster
- Good: Every tool invocation appears in the trace log with its full typed argument record
- Bad: Stdio transport adds latency; each tool call crosses a process boundary rather than executing in-process

#### Direct subprocess from agents

- Good: Zero additional infrastructure; agents call `kubectl` directly with no intermediary
- Bad: Direct subprocess calls with string-interpolated arguments are the canonical command-injection vector; Vigil's eval scenarios include adversarial pod names and StatefulSet selectors that would inject shell metacharacters into a `kubectl ... -l name=$bad` invocation. The MCP typed-argument boundary makes that class of failure structurally impossible.

#### Thin shell-script wrappers

- Good: Reduces the Go infrastructure requirement; wrappers can be added without a build step
- Bad: Shell-script wrappers around `kubectl`/`ssh`/`nixos-rebuild` would still concatenate arguments through bash word-splitting; auditing every wrapper for safe quoting is a moving target every time a new tool is added. MCP's typed JSON arguments cross the wire as structured data, never as a shell-interpreted string.

## More Information

- Go implementation choice: [`0003-go-mcp-servers.md`](0003-go-mcp-servers.md)
