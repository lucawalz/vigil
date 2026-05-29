# Eval Campaign Aggregation Report

Total runs: 5 across 1 models and 5 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 5 | 0.00 | — | — | 0.00 (0/1) | 0.00 | 0.00 | 85569/1435 | 13 | 2 |

## Per-Scenario Summary

0/12 passed, 1/12 out-of-scope, 0/12 agent-failed, 4/12 infra-error, 0/12 gate-uncertain, 7/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | no data | — | — | — | — |
| k8s-2g | no data | — | — | — | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
| os-1 | 1 | abort | 0.00 | — | — |
| os-1g | 1 | abort | 0.00 | — | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | abort | 0.00 | — | — |
| deceptive-2 | no data | — | — | — | — |
| disk-pressure | 1 | success | 0.00 | 153.02 | — |
| live-quota-injected | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| os-1 | os | — | N/A |
| os-1g | os | — | N/A |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | — | N/A |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign — std values omitted._
