# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 7 | 0.86 | 209.60 | 107.95 | 0.71 (5/7) | 0.57 | 0.00 | 79164.43/1756.43 | 13.29 | 7.14 |

## Per-Scenario Summary

5/7 passed, 1/7 out-of-scope, 1/7 agent-failed, 0/7 infra-error, 0/7 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 270.60 | — |
| k8s-2g | 1 | success | 1.00 | 276.90 | — |
| k8s-3g | 1 | success | 1.00 | 275.84 | — |
| k8s-4g | 1 | success | 1.00 | 138.57 | — |
| k8s-5g | 1 | success | 1.00 | 276.20 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | success | 0.00 | 234.08 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 19.47 | — |

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
