# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.85 | 236.34 | 139.09 | 0.85 (33/39) | 0.00 | 0.08 | 1.00 | 124313.33/5083.85 | 11.77 | 6.46 |

## Per-Scenario Summary

12/13 passed, 0/13 out-of-scope, 1/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 3 | success | 1.00 | 249.96 | 29.81 |
| k8s-2g | 3 | success | 1.00 | 241.60 | 36.41 |
| k8s-3g | 3 | success | 1.00 | 247.83 | 31.75 |
| k8s-4g | 3 | success | 1.00 | 235.88 | 42.89 |
| k8s-5g | 3 | success | 1.00 | 300.66 | 94.90 |
| k8s-rollback-1 | 3 | rollback_succeeded | 1.00 | 572.34 | 32.60 |
| os-1 | 3 | escalated | 0.67 | 168.18 | 99.53 |
| os-1g | 3 | success | 1.00 | 185.30 | 20.92 |
| os-drift-sysctl | 3 | success | 1.00 | 74.43 | 26.11 |
| os-stale-generation | 3 | success | 0.67 | 180.59 | 46.26 |
| deceptive-2 | 3 | escalated | 0.00 | 331.08 | 7.45 |
| disk-pressure | 3 | escalated | 0.67 | 233.95 | 113.15 |
| live-quota-injected | 3 | escalated | 1.00 | 49.33 | 37.62 |

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
| os-1 | os | 2/3 | 0.67 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
