# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 7 | 0.29 | 467.65 | 25.13 | 0.67 (2/3) | 0.43 | 0.00 | 77261/1406.17 | 11.67 | 5.50 |

## Per-Scenario Summary

2/7 passed, 1/7 out-of-scope, 2/7 agent-failed, 2/7 infra-error, 0/7 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 485.42 | — |
| k8s-2g | 1 | abort | 0.00 | — | — |
| k8s-3g | 1 | setup_error | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 449.88 | — |
| k8s-5g | 1 | setup_error | 0.00 | — | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | success | 0.00 | 440.53 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 0.00 | 0.84 | — |

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

---

_Single-seed campaign — std values omitted._
