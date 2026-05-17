# Architecture Decision Records

Architecture Decision Records (ADRs) document significant design choices, the context that led to them, and their trade-offs. ADRs use the [MADR 4.0.0](https://adr.github.io/madr/) format with two Vigil-specific conventions: each rejected alternative under "Pros and Cons of the Options" names a specific failure mode in the Vigil context (not a generic category), and the Consequences section includes a `Validation Status` field tying the decision to a Phase verification or production validation event.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-pydantic-ai-agent-framework.md) | Pydantic AI as agent orchestration framework | Accepted |
| [0002](0002-mcp-exclusive-tool-surface.md) | MCP as exclusive agent tool surface | Accepted |
| [0003](0003-go-mcp-servers.md) | Go for MCP server implementations | Accepted |
| [0004](0004-nixos-dead-mans-switch.md) | NixOS generations as dead-man's switch | Accepted |
| [0005](0005-multi-agent-architecture.md) | Dedicated-role multi-agent architecture | Accepted |
| [0006](0006-openai-compatible-provider-interface.md) | OpenAI-compatible provider interface | Superseded by [0014](0014-multi-adapter-model-factory.md) |
| [0007](0007-deterministic-fault-injection.md) | Shell-script-based deterministic fault injection | Accepted |
| [0008](0008-evaluation-model-selection.md) | Evaluation model selection | Accepted |
| [0009](0009-hetzner-cluster-provisioning.md) | Hetzner cluster provisioning | Accepted |
| [0010](0010-github-actions-eval-runner.md) | GitHub Actions eval campaign runner | Accepted |
| [0011](0011-deterministic-watchdog.md) | Deterministic Watchdog | Accepted |
| [0012](0012-empirically-calibrated-rollback-deadline.md) | Empirically-calibrated dead-man's switch deadline | Accepted |
| [0013](0013-gitops-k8s-remediation.md) | K8s-layer remediation via GitOps | Accepted |
| [0014](0014-multi-adapter-model-factory.md) | Multi-adapter model factory via Pydantic AI | Accepted |

Architecture-level rationale that spans multiple ADRs lives in [`docs/architecture/`](../architecture/).

## Adding an ADR

Create a new file `NNNN-title-in-kebab-case.md` using this template:

````markdown
---
status: Proposed | Accepted | Superseded by [ADR-MMMM](MMMM-...)
date: YYYY-MM-DD
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-NNNN: Title

## Context and Problem Statement

Why did this decision need to be made? What forces, constraints, or trade-offs were in play?

## Decision Drivers

- driver 1
- driver 2

## Considered Options

- chosen option
- rejected option 1
- rejected option 2

## Decision Outcome

Chosen option: "chosen option", because [concise rationale].

### Consequences

- Good: ...
- Bad: ...

**Validation Status:** Verified — Phase N VERIFICATION.md (or "Pending — Phase N", or a production validation citation)

### Confirmation

[testable criteria — how to verify the decision still holds]

### Pros and Cons of the Options

#### chosen option
- Good: ...
- Bad: ...

#### rejected option 1
- Good: ...
- Bad: [specific failure mode in the Vigil context, >= 15 words; not a generic category]

#### rejected option 2
- Good: ...
- Bad: [specific failure mode in the Vigil context, >= 15 words]

## More Information

[cross-references to relevant architecture docs and ADRs]
````
