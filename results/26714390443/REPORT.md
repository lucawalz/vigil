# Eval Campaign Aggregation Report

Total runs: 5 across 1 models and 5 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 5 | 0.60 | 195.75 | 26.69 | 0.75 (3/4) | 0.40 | 0.00 | 461350.50/3673.75 | 30.25 | 5 |

## Per-Scenario Summary

3/13 passed, 0/13 out-of-scope, 1/13 agent-failed, 1/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 8/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | no data | — | — | — | — |
| k8s-2g | no data | — | — | — | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
| k8s-rollback-1 | no data | — | — | — | — |
| os-1 | 1 | success | 1.00 | 193.82 | — |
| os-1g | 1 | success | 1.00 | 170.07 | — |
| os-drift-sysctl | 1 | escalated | 0.00 | 75.50 | — |
| os-stale-generation | 1 | abort | 0.00 | — | — |
| deceptive-2 | no data | — | — | — | — |
| disk-pressure | 1 | escalated | 1.00 | 223.34 | — |
| live-quota-injected | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | — | N/A |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
