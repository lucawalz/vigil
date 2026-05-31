# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 13 | 0.85 | 194.56 | 95.89 | 0.92 (11/12) | 0.69 | 0.00 | 138179.69/1953.31 | 15 | 6.38 |

## Per-Scenario Summary

11/13 passed, 1/13 out-of-scope, 0/13 agent-failed, 1/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 273.20 | — |
| k8s-2g | 1 | success | 1.00 | 295.02 | — |
| k8s-3g | 1 | inject_did_not_break | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 277.73 | — |
| k8s-5g | 1 | success | 1.00 | 275.49 | — |
| k8s-rollback-1 | 1 | success | 1.00 | 296.23 | — |
| os-1 | 1 | success | 1.00 | 168.06 | — |
| os-1g | 1 | success | 1.00 | 158.28 | — |
| os-drift-sysctl | 1 | success | 1.00 | 137.97 | — |
| os-stale-generation | 1 | success | 1.00 | 172.77 | — |
| deceptive-2 | 1 | success | 0.00 | 229.51 | — |
| disk-pressure | 1 | escalated | 1.00 | 47.91 | — |
| live-quota-injected | 1 | escalated | 1.00 | 37.52 | — |

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
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
