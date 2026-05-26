# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 7 | 0.71 | 236.74 | 105.25 | 0.83 (5/6) | 0.57 | 0.00 | 100698.29/1907 | 12.57 | 6.71 |

## Per-Scenario Summary

5/12 passed, 1/12 out-of-scope, 1/12 agent-failed, 0/12 infra-error, 0/12 gate-uncertain, 5/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 275.30 | — |
| k8s-2g | 1 | success | 1.00 | 304.47 | — |
| k8s-3g | 1 | inject_did_not_break | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 277.03 | — |
| k8s-5g | 1 | success | 1.00 | 277.18 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | success | 0.00 | 232.67 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 49.71 | — |

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
