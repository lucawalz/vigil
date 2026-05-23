# Eval Campaign Aggregation Report

Total runs: 5 across 1 models and 5 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 5 | 0.00 | — | — | — | 0.00 | 0.00 | 0/0 | 0 | 1 |

## Per-Scenario Summary

0/5 passed, 0/5 out-of-scope, 5/5 agent-failed, 0/5 infra-error, 0/5 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | abort | 0.00 | — | — |
| k8s-2g | 1 | flux_degraded | 0.00 | — | — |
| k8s-3g | 1 | flux_degraded | 0.00 | — | — |
| k8s-4g | 1 | flux_degraded | 0.00 | — | — |
| k8s-5g | 1 | flux_degraded | 0.00 | — | — |
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
| k8s-4g | k8s | — | N/A |
| k8s-5g | k8s | — | N/A |

---

_Single-seed campaign — std values omitted._
