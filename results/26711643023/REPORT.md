# Eval Campaign Aggregation Report

Total runs: 12 across 1 models and 12 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 12 | 0.67 | 210.67 | 86.31 | 0.80 (8/10) | 0.58 | 0.00 | 152993.09/2075.91 | 16.36 | 6.27 |

## Per-Scenario Summary

8/13 passed, 2/13 out-of-scope, 0/13 agent-failed, 2/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 1/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 277.39 | — |
| k8s-2g | 1 | success | 1.00 | 284.00 | — |
| k8s-3g | 1 | inject_did_not_break | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 277.51 | — |
| k8s-5g | 1 | success | 1.00 | 279.27 | — |
| k8s-rollback-1 | no data | — | — | — | — |
| os-1 | 1 | success | 1.00 | 171.77 | — |
| os-1g | 1 | success | 1.00 | 179.02 | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | success | 1.00 | 177.56 | — |
| deceptive-2 | 1 | success | 0.00 | 231.28 | — |
| disk-pressure | 1 | success | 0.00 | 158.51 | — |
| live-quota-injected | 1 | escalated | 1.00 | 38.84 | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| k8s-1g | k8s | — | N/A |
| k8s-2g | k8s | — | N/A |
| k8s-3g | k8s | — | N/A |
| k8s-4g | k8s | — | N/A |
| k8s-5g | k8s | — | N/A |
| live-quota-injected | k8s | — | N/A |
| deceptive-2 | k8s | — | N/A |
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign — std values omitted._
