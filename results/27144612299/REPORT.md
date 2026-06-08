# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.51 | 389.14 | 93.63 | 0.74 (20/27) | 0.00 | 0.00 | — | 140644.23/2894.10 | 13.42 | 5.52 |

## Per-Scenario Summary

10/13 passed, 0/13 out-of-scope, 3/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 3 | success | 1.00 | 322.78 | 15.44 |
| k8s-2g | 3 | success | 1.00 | 440.04 | 33.05 |
| k8s-3g | 3 | success | 1.00 | 401.04 | 4.70 |
| k8s-4g | 3 | success | 1.00 | 413.67 | 19.41 |
| k8s-5g | 3 | success | 1.00 | 483.07 | 185.06 |
| k8s-rollback-1 | 3 | escalated | 0.00 | 287.49 | — |
| os-1 | 3 | escalated | 0.33 | 327.78 | 166.06 |
| os-1g | 3 | escalated | 0.00 | 411.81 | — |
| os-drift-sysctl | 3 | success | 0.33 | 265.56 | — |
| os-stale-generation | 3 | success | 0.33 | 321.18 | — |
| deceptive-2 | 3 | escalated | 0.00 | 501.89 | 16.16 |
| disk-pressure | 3 | escalated | 0.33 | 220.43 | 87.37 |
| live-quota-injected | 3 | escalated | 0.33 | 473.92 | 264.54 |

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
| os-1 | os | 1/2 | 0.50 |
| os-1g | os | 0/1 | 0.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/2 | 0.50 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
