# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 7 | 0.14 | 428.93 | — | 1.00 (1/1) | 0.14 | 0.00 | 20022.57/373.29 | 3 | 1.57 |

## Per-Scenario Summary

1/7 passed, 0/7 out-of-scope, 0/7 agent-failed, 6/7 infra-error, 0/7 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 428.93 | — |
| k8s-2g | 1 | setup_error | 0.00 | — | — |
| k8s-3g | 1 | setup_error | 0.00 | — | — |
| k8s-4g | 1 | setup_error | 0.00 | — | — |
| k8s-5g | 1 | setup_error | 0.00 | — | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | setup_error | 0.00 | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | setup_error | 0.00 | — | — |

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
