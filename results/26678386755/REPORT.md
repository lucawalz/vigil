# Eval Campaign Aggregation Report

Total runs: 4 across 1 models and 4 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 4 | 0.25 | 177.17 | — | 1.00 (1/1) | 0.25 | 0.00 | 287381/3506 | 26 | 11 |

## Per-Scenario Summary

1/12 passed, 0/12 out-of-scope, 0/12 agent-failed, 3/12 infra-error, 0/12 gate-uncertain, 8/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | no data | — | — | — | — |
| k8s-2g | no data | — | — | — | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
| os-1 | 1 | abort | 0.00 | — | — |
| os-1g | 1 | success | 1.00 | 177.17 | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | abort | 0.00 | — | — |
| deceptive-2 | no data | — | — | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| os-1 | os | — | N/A |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | — | N/A |

---

_Single-seed campaign — std values omitted._
