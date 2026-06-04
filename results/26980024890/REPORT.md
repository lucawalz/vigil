# Eval Campaign Aggregation Report

Total runs: 8 across 1 models and 8 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 8 | 0.62 | 370.82 | 108.21 | 0.83 (5/6) | 0.00 | 0.00 | — | 145187.67/3947.50 | 19.17 | 10.17 |

## Per-Scenario Summary

5/13 passed, 0/13 out-of-scope, 1/13 agent-failed, 2/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 5/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 431.49 | — |
| k8s-2g | 1 | abort | 0.00 | — | — |
| k8s-3g | 1 | success | 1.00 | 438.52 | — |
| k8s-4g | 1 | success | 1.00 | 431.14 | — |
| k8s-5g | 1 | success | 1.00 | 369.03 | — |
| k8s-rollback-1 | 1 | success | 1.00 | 183.93 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | flux_degraded | 0.00 | 1164.75 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | abort | 0.00 | — | — |

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
