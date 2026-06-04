# Eval Campaign Aggregation Report

Total runs: 10 across 1 models and 8 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 10 | 0.40 | 296.50 | 190.32 | 1.00 (5/5) | 0.10 | 0.00 | — | 89869.75/2429.25 | 11.75 | 5.88 |

## Per-Scenario Summary

4/13 passed, 0/13 out-of-scope, 2/13 agent-failed, 1/13 infra-error, 1/13 gate-uncertain, 0/13 awaiting-review, 5/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 285.54 | — |
| k8s-2g | 1 | gate_failed | 0.00 | 467.39 | — |
| k8s-3g | 2 | diagnosis_timeout | 0.00 | — | — |
| k8s-4g | 2 | abort | 0.00 | — | — |
| k8s-5g | 1 | success | 1.00 | 296.00 | — |
| k8s-rollback-1 | 1 | success | 1.00 | 535.11 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | diagnosis_timeout | 0.00 | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 69.33 | — |

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

_Note: std values computed from 2 seeds per cell; treat as directional only._
