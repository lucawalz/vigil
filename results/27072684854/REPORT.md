# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.54 | 187.81 | 68.79 | 0.73 (8/11) | 0.08 | 0.00 | — | 131373.73/6078.82 | 14.55 | 8 |

## Per-Scenario Summary

7/13 passed, 1/13 out-of-scope, 3/13 agent-failed, 2/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 277.30 | — |
| k8s-2g | 1 | success | 1.00 | 218.21 | — |
| k8s-3g | 1 | success | 1.00 | 216.86 | — |
| k8s-4g | 1 | success | 1.00 | 217.50 | — |
| k8s-5g | 1 | abort | 0.00 | — | — |
| k8s-rollback-1 | 1 | flux_degraded | 0.00 | 996.86 | — |
| os-1 | 1 | success | 1.00 | 157.15 | — |
| os-1g | 1 | success | 1.00 | 167.91 | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | success | 1.00 | 59.74 | — |
| deceptive-2 | 1 | flux_degraded | 0.00 | 649.08 | — |
| disk-pressure | 1 | success | 0.00 | 79.89 | — |
| live-quota-injected | 1 | escalated | 0.00 | 40.78 | — |

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
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign — std values omitted._
