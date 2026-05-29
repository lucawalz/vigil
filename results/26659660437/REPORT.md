# Eval Campaign Aggregation Report

Total runs: 2 across 1 models and 2 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 2 | 0.50 | 153.54 | — | 1.00 (1/1) | 0.50 | 0.00 | 94268/1455.50 | 10 | 5.50 |

## Per-Scenario Summary

1/12 passed, 0/12 out-of-scope, 0/12 agent-failed, 1/12 infra-error, 0/12 gate-uncertain, 10/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | no data | — | — | — | — |
| k8s-2g | no data | — | — | — | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
| os-1 | 1 | setup_error | 0.00 | — | — |
| os-1g | 1 | success | 1.00 | 153.54 | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | no data | — | — | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| os-1 | os | — | N/A |
| os-1g | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
