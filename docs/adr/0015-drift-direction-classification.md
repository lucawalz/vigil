---
status: Accepted
date: 2026-05-19
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0015: Drift-direction classification across K8s and NixOS layers

> Updated 2026-06-14: clarified that classification is two-way (live versus the baseline branch, never `main`) and documented the `both_drift` escalation class, including structured `expected_drift_classification` grading on the model's `drift_classification` field.

## Context and Problem Statement

PR #77 exposed a structural gap: the agent emitted a corrective `git_commit` for a K8s fault whose in-repo manifest was already correct. The resulting PR carried 0 additions and 7 deletions; the cluster healed only because Flux's natural reconcile poll reapplied the unchanged manifest. The agent did not drive the recovery.

The root cause is that the agent had no concept of drift direction. K8s and NixOS faults each come in two forms: a live-cluster mutation against a correct manifest (live drift, fixed by reconciling from the repo), or a committed bad value in the repo that the cluster is faithfully applying (in-repo drift, fixed by committing a correction). The agent treated every K8s fault as in-repo drift and never encountered an in-repo scenario — so its remediation path had no real surface to operate on, and the eval campaign had no coverage of the in-repo cells.

## Decision Drivers

- PR #77 demonstrates the live-drift / in-repo-drift conflation causes structurally invalid recovery: the agent commits to an already-correct manifest and Flux heals the cluster independently
- The thesis claim "reversible by construction" requires the correct reversal primitive per fault type; the wrong primitive produces invalid recovery evidence
- Both K8s and NixOS layers carry either form of drift; four action classes are necessary and sufficient to cover every combination
- The eval campaign must score each quadrant independently; zero g-variant scenarios existed before this decision

## Considered Options

- 2×2 action surface keyed by layer × drift origin (`flux_reconcile`, `git_commit_k8s`, `nixos_rebuild`, `git_commit_nix`)
- Single `git_commit` action for all faults regardless of drift direction
- Direction inference deferred to the Remediation agent
- No classification; always issue `flux_reconcile` or `nixos_rebuild` regardless of manifest state

## Decision Outcome

Chosen option: "2×2 action surface keyed by layer × drift origin", because it assigns a distinct, correct remediation primitive to every fault quadrant, eliminates the empty-PR failure mode, and gives the eval campaign a separately scoreable in-repo cell for each layer.

The Diagnosis agent inspects both live cluster state and `chore/eval-cluster-baseline` HEAD for each affected resource, computes drift direction, and emits one of the four actions. The Remediation agent executes the emitted action without further diagnosis.

### Two-way comparison and the both_drift escalation class

Classification operates entirely within a two-way model: live cluster state versus the Flux-tracked baseline branch (`chore/eval-cluster-baseline`). The comparison never consults the repo `main` branch; there is no three-way comparison.

Within that two-way model, each affected resource falls into one of four drift classes:

- `live_only_drift` — live state mutated against a correct baseline manifest; reconciling from the baseline restores health (`flux_reconcile` / `nixos_rebuild`)
- `declared_drift` — the baseline carries a committed bad value the cluster is faithfully applying; committing a correction restores health (`git_commit_k8s` / `git_commit_nix`)
- `both_drift` — live and declared each independently invalid, such that neither reconciling to declared nor committing live restores a healthy system; the agent escalates rather than emitting a corrective action
- `no_drift` — live and declared agree and both are healthy; no action

`both_drift` is therefore an explicit escalation outcome, not a remediation primitive. Because classification is two-way, an injected fault that mutates both the live state and the baseline manifest into mutually incompatible invalid states leaves the agent with no single reversal direction that recovers the system, and the correct behaviour is to escalate. Scenarios whose ground truth *is* the drift direction assert it via `expected_drift_classification` and are scored on the model's structured, validated `drift_classification` field rather than free-text keyword matching, so a correct classification is never rejected on prose vocabulary.

### Consequences

- Good: Each of the four quadrants maps to an unambiguous action; the eval campaign can score layer-classification and direction-classification independently
- Good: Live-drift faults never produce a commit; in-repo drift faults never issue a bare reconcile; the structural mismatch that caused PR #77 is eliminated
- Good: Action vocabulary is a closed enum; adding a new fault type requires categorising it into an existing quadrant, not inventing a new action class
- Bad: Diagnosis agent must fetch both live object YAML and `chore/eval-cluster-baseline` HEAD for every fault; adds two remote reads per diagnosis, increasing latency
- Bad: The g-variant scenarios increase eval campaign cost roughly proportionally to the existing scenario count
- Bad: The K8s live-drift (`flux_reconcile`) quadrant is implemented in the action enum but has no eval scenario coverage; the campaign cannot yet score that cell empirically

**Validation Status:** Partial. The in-repo-drift quadrants are covered by g-variant scenarios (k8s-1g..5g for `git_commit_k8s`, os-1g for `git_commit_nix`) and exercised in the full 13-scenario campaign; the K8s live-drift (`flux_reconcile`) quadrant has no scenario coverage yet.

### Confirmation

The decision holds as long as:

- The `DiagnosisReport.recommended_action` enum in `agents/diagnosis/src/diagnosis/models.py` carries all four actions (`flux_reconcile`, `git_commit_k8s`, `nixos_rebuild`, `git_commit_nix`)
- `eval/scenarios/k8s-{1..5}g/scenario.yaml` each carry `expected_action: git_commit_k8s`
- `eval/scenarios/os-1g/scenario.yaml` carries `expected_action: git_commit_nix`
- `eval/scenarios/{os-1,os-drift-sysctl,os-stale-generation}/scenario.yaml` each carry `expected_action: nixos_rebuild`
- `eval/scenarios/deceptive-2/scenario.yaml` covers the `both_drift` class, carrying live and declared state in different invalid forms; the expected outcome is escalation rather than any corrective action
- No g-variant run opens a PR against `main`; `RunRecord.agent_branch` targets `chore/eval-cluster-baseline` exclusively
- Each g-variant scenario returns `outcome == "success"` in the campaign

### Pros and Cons of the Options

#### 2×2 action surface keyed by layer × drift origin

- Good: Four actions cover every layer–direction combination; both diagnosis and remediation are unambiguous
- Good: Eval campaign can score each quadrant independently, producing four separate accuracy metrics
- Bad: Diagnosis agent must inspect `chore/eval-cluster-baseline` HEAD in addition to live cluster state, adding a remote read step to the diagnosis flow

#### Single `git_commit` action for all faults

- Bad: For live-drift faults the in-repo manifest is already correct; the agent commits a no-op edit — exactly the PR #77 failure mode, where additions=0 and the cluster healed only because Flux's natural poll reapplied the unchanged manifest. The thesis cannot claim the agent drove the recovery.

#### Direction inference deferred to the Remediation agent

- Bad: The Remediation agent receives only the emitted action from Diagnosis; deferring direction resolution forces it to fetch `chore/eval-cluster-baseline` state and re-execute diagnosis logic. This splits "what is wrong" across two agents, breaking the contract that Diagnosis emits a complete action and Remediation executes without further reasoning — the same violation that ADR-0005 introduced dedicated roles to prevent.

#### No classification; always reconcile

- Bad: Flux reconcile applies the current `chore/eval-cluster-baseline` HEAD to the cluster; when `chore/eval-cluster-baseline` carries a committed bad manifest (the g-variant inject case), reconciling propagates the fault rather than correcting it. The cluster enters a restart loop recoverable only by reverting the commit, but the agent has no signal to revert because the reconcile completed successfully from Flux's perspective.

## Operational constraints

**g-variant scenarios must run sequentially.** `chore/eval-cluster-baseline` is a single shared branch tracked by the Flux `GitRepository` (`gotk-sync.yaml:11`). Concurrent g-variant `inject.sh` runs clobber each other's commits on `chore/eval-cluster-baseline`, producing undefined cluster state.

**`chore/eval-cluster-baseline` is a permanent operational branch.** Deleting it breaks the Hetzner cluster's GitOps: Flux loses its source branch and all kustomisations fail to reconcile. The branch must persist for the lifetime of the eval cluster.

## More Information

- NixOS auto-reconciler delivering in-repo config to Hetzner workers: `docs/adr/0004-nixos-dead-mans-switch.md`
- Inject/reset script pair contract that g-variant scenarios extend: `docs/adr/0007-deterministic-fault-injection.md`
- Deterministic watchdog health gate validating remediation outcome: `docs/adr/0011-deterministic-watchdog.md`
- K8s-layer GitOps remediation (`git_commit_k8s` path): `docs/adr/0013-gitops-k8s-remediation.md`
