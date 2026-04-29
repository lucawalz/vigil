# Architecture Decision Records

Architecture Decision Records (ADRs) document significant design choices, the context that led to them, and their trade-offs.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-pydantic-ai-agent-framework.md) | Pydantic AI as agent orchestration framework | Accepted |
| [0002](0002-mcp-exclusive-tool-surface.md) | MCP as exclusive agent tool surface | Accepted |
| [0003](0003-go-mcp-servers.md) | Go for MCP server implementations | Accepted |
| [0004](0004-nixos-dead-mans-switch.md) | NixOS generations as dead-man's switch | Accepted |
| [0005](0005-multi-agent-architecture.md) | Dedicated-role multi-agent architecture | Accepted |
| [0006](0006-openai-compatible-provider-interface.md) | OpenAI-compatible provider interface | Accepted |
| [0007](0007-deterministic-fault-injection.md) | Shell-script-based deterministic fault injection | Accepted |
| [0008](0008-evaluation-model-selection.md) | Evaluation model selection | Accepted |

## Adding an ADR

Create a new file `NNNN-title-in-kebab-case.md` using this template:

```markdown
# ADR-NNNN: Title

**Status**: Proposed | Accepted | Superseded by [ADR-MMMM](MMMM-...)

## Context

Why did this decision need to be made? What forces, constraints, or trade-offs were in play?

## Decision

The decision that was made.

## Consequences

What becomes easier or harder as a result?
```
