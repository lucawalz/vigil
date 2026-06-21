---
status: Accepted
date: 2026-06-21
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0017: Evaluation oracle-leak remediation and rollback scoring resolution

## Context and Problem Statement

An adversarial fact-check of the thesis evaluation found that the harness disclosed ground truth to the Diagnosis agent, inflating the scored metrics. Two leak classes reached the agent before it reasoned. First, the scenario's forbidden actions were both pre-filtered out of the agent's tool surface and named in a "Scenario constraint" prompt block that instructed the agent to escalate, steering every escalation scenario toward the correct answer. Second, the alert payload embedded the scenario identity: `annotations.summary` and `fingerprint` carried the scenario id and the `groupKey` carried an `eval/` tell, so the agent could recognise the scenario rather than diagnose it.

Separately, the `k8s-rollback-1` scenario (an OOM fix masked by a live-only ResourceQuota) raised a scoring question. The run that commits the memory fix triggers an automatic rollback when the quota rejects the corrected pod, whereas a run that escalates does not. It was unclear whether crediting the commit-then-rollback path while not crediting an escalation biased the metric against conservative models.

## Decision Drivers

- The thesis reports the evaluation as an unbiased measure of autonomous diagnosis; any ground truth reaching the agent invalidates that claim
- Forbidden actions must still gate scoring so a destructive action fails the run, without becoming visible to the agent as a hint
- `k8s-rollback-1` exists to demonstrate reversibility; its scoring must reward the action that exercises the rollback machinery, not penalise it
- The frozen baseline must not change behaviour without a re-run; documentation-only clarification is preferred where the metric is already correct

## Considered Options

- Remove the leaks at their source, keep forbidden-action checking as scoring-only, and resolve `k8s-rollback-1` as working-as-designed with no scenario or scoring change
- Additionally credit a safe escalation on `k8s-rollback-1` alongside the commit-then-rollback path (accept-both)
- Hide the live ResourceQuota from the runtime diagnosis path so committing becomes unambiguous (Option C)

## Decision Outcome

Chosen option: "Remove the leaks at their source, keep forbidden-action checking as scoring-only, and resolve `k8s-rollback-1` as working-as-designed."

The forbidden-actions list no longer pre-filters the tool surface or appears in any prompt block; `_check_forbidden_actions` and the `forbidden_action_violations` field retain it purely for scoring. The alert payload now carries a generic summary, a hashed fingerprint, and a realistic `groupKey` with no `eval/` tell.

`k8s-rollback-1` is left unchanged. A live single-seed run (qwen3.5, commit `3bf17a05`) confirmed the scenario behaves as designed without any leak: the agent committed the 96Mi memory fix, the masked live ResourceQuota rejected the corrected pod, the watchdog observed persistent degradation, and the orchestrator automatically reverted the merge, producing outcome `rollback_succeeded` and demonstrating reversibility end-to-end on the live cluster. Crediting the commit-then-rollback path is correct because that path is the one that exercises the reversal primitive the scenario exists to demonstrate; an escalation is safe but leaves reversibility undemonstrated and is legitimately uncredited for this scenario.

### Per-run success_rate is provisional

A successful rollback writes `success_rate=False` into the per-run record because the orchestrator's `success_rate` formula folds in the pre-rollback watchdog verdict (`degraded=True`) and the watchdog is not re-evaluated after the revert. Aggregation reconciles this: a credit-bearing outcome (`rollback_succeeded`, or an escalation whose `expected_action` is `escalate`) is scored against the scenario's `expected_outcome` or `expected_action`, and `success_rate` is finalised there. The aggregate is the authoritative metric; the per-run field is provisional. This invariant was the source of an earlier misreading that the commit-then-rollback path was failing.

### Consequences

- Good: The scored metrics no longer contain any ground truth reaching the agent; escalation- and sysctl-class scenarios are expected to score below the leaky numbers, which is the honest result
- Good: `k8s-rollback-1` demonstrates the rollback primitive on every run in which the agent commits, with no scenario engineering
- Good: Forbidden-action gating still fails destructive runs, preserving the safety metric
- Bad: The provisional-versus-authoritative split between per-run and aggregate `success_rate` is non-obvious and must be read with the aggregate as the source of truth
- Bad: A model that escalates on `k8s-rollback-1` scores as a miss; if conservative models do so consistently, the scenario measures rollback demonstration rather than diagnosis quality for those runs

**Validation Status:** Partial. The leak removals are covered by the unit suite and a single-seed live run confirmed `k8s-rollback-1` and `live-quota-injected` behave as intended; the full three-model × three-seed campaign on the frozen baseline is pending.

### Confirmation

The decision holds as long as:

- No scenario field, whether forbidden actions or scenario id, reaches the agent via tool filtering or any prompt or context block; forbidden actions appear only in `_check_forbidden_actions`
- The alert payload carries no scenario id in `annotations.summary`, `fingerprint`, or `groupKey`
- `eval/scenarios/k8s-rollback-1/scenario.yaml` retains `expected_action: git_commit_k8s` and `expected_outcome: rollback_succeeded` with no `accept_escalate_as_safe` flag
- `_correct_outcome_success` and `_correct_escalation_success` run during aggregation, finalising `success_rate` for credit-bearing outcomes against the scenario's expected outcome

### Pros and Cons of the Options

#### Remove the leaks at source; resolve k8s-rollback-1 as working-as-designed

- Good: Eliminates every ground-truth channel while preserving forbidden-action scoring and the rollback demonstration
- Good: Introduces no behaviour change to the frozen baseline beyond the leak removals already committed
- Bad: Leaves the provisional per-run `success_rate` in place, requiring readers to treat the aggregate as authoritative

#### Accept-both: credit safe escalation alongside commit-then-rollback

- Bad: A campaign in which every model escalates would record zero rollback demonstrations, gutting the reversibility evidence the scenario exists to produce; the live run shows the rollback path does fire, so the added credit provides no benefit and reintroduces that risk

#### Option C: hide the live ResourceQuota from the runtime diagnosis path

- Bad: Requires brittle string-parsing of the concatenated pod-status text to separate runtime failure from admission rejection, changes no score because the agent already commits and the rollback already fires, and adds a maintenance hazard for a failure mode the live evidence shows does not occur

## More Information

- Evaluation model selection and superseded campaigns: `docs/adr/0008-evaluation-model-selection.md`
- Deterministic watchdog health gate validating remediation outcome: `docs/adr/0011-deterministic-watchdog.md`
- Drift-direction classification and the `both_drift` escalation class: `docs/adr/0015-drift-direction-classification.md`
- Release tagging and the frozen baseline: `docs/adr/0016-release-tagging-and-changelog-automation.md`
