---
status: Accepted
date: 2026-04-22
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0007: Shell-script-based deterministic fault injection

## Context and Problem Statement

The evaluation campaign requires ground-truth labels (root-cause layer and correct repair action) for each run in order to compute classification accuracy metrics. Two concerns shape the injection approach:

1. **Reproducibility**: Each seed must start from an identical cluster state. Fault injection must be idempotent: running `inject.sh` twice produces the same fault, and `reset.sh` unconditionally restores the baseline regardless of agent actions taken during the run.
2. **Labeling**: The research questions require pre-labeled ground truth (root-cause layer, correct repair action) for each scenario before the agent runs. A fault with no stable label cannot be used to score agent accuracy.

The 12 scenario YAML stubs (covering K8s×5, OS×3, Cross×3, boundary×1 fault types) each require deterministic injection so that scenario K8s-1 always produces the same pod failure mode across all seeds and models.

## Decision Drivers

- Eval runs must be reproducible: same fault, same initial state, across all seeds
- Ground-truth labels must be fixed before each run; randomized injection produces no stable label
- Injection must be executable from outside the cluster so that OS-level faults cannot disable the injection mechanism
- Reset must be unconditional: idempotent shell scripts guarantee clean baseline regardless of prior agent actions

## Considered Options

- Shell-script-based idempotent fault injection (`inject.sh` / `reset.sh` pairs per scenario)
- Autonomous chaos engineering platform (Chaos Mesh / Litmus)
- Kubernetes operator-driven fault injection (CRD-based, running inside the cluster)

## Decision Outcome

Chosen option: "Shell-script-based idempotent fault injection", because it produces deterministic, pre-labeled ground truth for each run, executes from outside the cluster (making OS-layer faults injectable without circular dependencies), and requires no additional cluster infrastructure.

### Consequences

- Good: Deterministic injection produces reproducible ground truth for accuracy, MTTR, and action-class metrics
- Good: Each scenario can be tested independently and reset between runs without cluster re-provisioning
- Good: Scripts execute from the agent host, outside the cluster; OS-level fault scenarios cannot take down the injection mechanism
- Bad: Fault coverage is limited to the 12 pre-defined scenarios; injecting novel fault types requires authoring new scripts
- Bad: Script maintenance grows linearly with scenario count; complex multi-step faults require careful reset sequencing

**Validation Status:** Verified — 12 scenarios with idempotent inject/reset; reset before injection guarantees clean baseline; 71-run Hetzner campaign confirms identical initial state across all seeds.

### Confirmation

The 12 scenario directories under `eval/scenarios/` each contain `inject.sh` and `reset.sh`. The eval harness calls `reset.sh` before `inject.sh` for every run, confirmed in the campaign runner. Eval campaign results show consistent per-scenario pass rates across 3 seeds, confirming identical initial state.

### Pros and Cons of the Options

#### Shell-script-based idempotent fault injection

- Good: Zero additional cluster infrastructure; scripts are plain shell runnable on any Unix host with `kubectl` access
- Good: Ground truth is encoded in the script pair: the injected fault is known before the agent runs
- Bad: Scale requires manual authoring; adding fault type 13 means writing a new script pair, not configuring a platform

#### Autonomous chaos engineering platform (Chaos Mesh / Litmus)

- Good: Large library of pre-built fault types; no per-scenario scripting required
- Bad: Chaos Mesh injects faults non-deterministically by design: randomized pod kills, randomized network partitions. Vigil's research questions require pre-labelled ground truth (root-cause layer, correct repair action) for each run; a randomized fault has no stable label. The 12 scenario YAML stubs require deterministic injection so that scenario K8s-1 always produces the same pod failure mode.

#### Kubernetes operator-driven fault injection

- Good: Declarative CRD syntax; fault specifications are version-controlled Kubernetes manifests
- Bad: An injection operator running inside the cluster would itself be subject to the faults under test; injecting `kube-apiserver` failure modes would take down the operator that injects them. Idempotent shell scripts run from outside the cluster (the agent host), making cluster-down scenarios injectable without bootstrapping circular dependencies.

## More Information

- Scenario implementations: `eval/scenarios/` (12 directories, one per fault scenario)
- Eval harness campaign runner: `eval/`
- Scenario documentation: `docs/eval/scenarios/` (forthcoming)
