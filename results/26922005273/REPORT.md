# Eval Campaign Aggregation Report

Total runs: 4 across 1 models and 4 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 4 | 0.25 | 536.33 | — | 1.00 (1/1) | 0.00 | 0.00 | — | 34740/1487 | 5 | 3.67 |

## Per-Scenario Summary

1/13 passed, 0/13 out-of-scope, 2/13 agent-failed, 1/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 9/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 536.33 | — |
| k8s-2g | 1 | abort | 0.00 | — | — |
| k8s-3g | 1 | diagnosis_timeout | 0.00 | — | — |
| k8s-4g | 1 | diagnosis_timeout | 0.00 | — | — |
| k8s-5g | no data | — | — | — | — |
| k8s-rollback-1 | no data | — | — | — | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | no data | — | — | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| k8s-1g | k8s | — | N/A |
| k8s-2g | k8s | — | N/A |
| k8s-3g | k8s | — | N/A |
| k8s-4g | k8s | — | N/A |

---

_Single-seed campaign — std values omitted._
