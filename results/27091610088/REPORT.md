# Eval Campaign Aggregation Report

Total runs: 8 across 1 models and 8 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 8 | 0.75 | 194.41 | 80.28 | 0.75 (6/8) | 0.00 | 0.00 | — | 87413.50/4306.62 | 10.88 | 6.62 |

## Per-Scenario Summary

6/13 passed, 0/13 out-of-scope, 2/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 5/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 219.38 | — |
| k8s-2g | 1 | success | 1.00 | 216.01 | — |
| k8s-3g | 1 | success | 1.00 | 193.88 | — |
| k8s-4g | 1 | success | 1.00 | 217.90 | — |
| k8s-5g | 1 | success | 1.00 | 278.32 | — |
| k8s-rollback-1 | 1 | escalated | 0.00 | 83.43 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | escalated | 0.00 | 341.57 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 40.98 | — |

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

---

_Single-seed campaign — std values omitted._
