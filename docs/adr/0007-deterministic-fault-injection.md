# ADR-0007: Shell-script-based deterministic fault injection

**Status**: Accepted

## Context

The evaluation campaign requires ground-truth labels (root-cause layer, correct repair action) for each run in order to compute classification metrics. Two approaches were considered:

1. **Autonomous chaos engineering** (e.g. Chaos Mesh): randomly injects faults; non-deterministic; makes ground-truth labeling impractical
2. **Scripted injection**: each scenario is a pair of idempotent shell scripts (`inject.sh` / `reset.sh`) that apply and undo a specific fault

The research questions require controlled, reproducible conditions where the ground truth is known before the agent runs.

## Decision

Implement each of the 12 fault scenarios as a pair of idempotent shell scripts. The `inject.sh` script applies one fault; `reset.sh` restores the baseline. Scripts are stored in `eval/scenarios/<scenario-name>/`.

## Consequences

- Deterministic injection produces reproducible ground truth for accuracy, MTTR, and action-class metrics
- Each scenario can be tested independently and reset between runs without cluster re-provisioning
- Fault coverage is limited to the 12 pre-defined scenarios; injecting novel fault types requires new scripts
- Script maintenance grows linearly with scenario count; complex multi-step faults require careful reset sequencing
