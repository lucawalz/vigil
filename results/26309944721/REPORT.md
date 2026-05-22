# Eval Campaign Aggregation Report

Total runs: 3 across 1 models and 3 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 3 | 0.00 | — | — | 0.00 (0/2) | 0.00 | 0.00 | 27070/509.67 | 5 | 0.67 |

## Per-Scenario Summary

0/3 passed, 0/3 out-of-scope, 2/3 agent-failed, 1/3 infra-error, 0/3 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | escalated | 0.00 | 34.30 | — |
| k8s-2g | 1 | escalated | 0.00 | 35.52 | — |
| k8s-3g | 1 | setup_error | 0.00 | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
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

---

_Single-seed campaign — std values omitted._
