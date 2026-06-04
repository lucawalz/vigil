# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 13 | 0.38 | 303.79 | 171.34 | 0.50 (3/6) | 0.00 | 0.00 | — | 130294.71/3458.57 | 14.29 | 5.86 |

## Per-Scenario Summary

5/13 passed, 1/13 out-of-scope, 1/13 agent-failed, 6/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 296.99 | — |
| k8s-2g | 1 | success | 0.00 | 151.35 | — |
| k8s-3g | 1 | abort | 0.00 | — | — |
| k8s-4g | 1 | diagnosis_timeout | 0.00 | — | — |
| k8s-5g | 1 | success | 1.00 | 282.54 | — |
| k8s-rollback-1 | 1 | success | 1.00 | 497.52 | — |
| os-1 | 1 | abort | 0.00 | — | — |
| os-1g | 1 | abort | 0.00 | — | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | abort | 0.00 | — | — |
| deceptive-2 | 1 | escalated | 1.00 | 402.19 | — |
| disk-pressure | 1 | abort | 0.00 | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 39.73 | — |

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
| k8s-rollback-1 | k8s | — | N/A |
| os-1 | os | — | N/A |
| os-1g | os | — | N/A |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | — | N/A |
| disk-pressure | os | — | N/A |

---

_Single-seed campaign — std values omitted._
