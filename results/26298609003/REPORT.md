# Eval Campaign Aggregation Report

Total runs: 1 across 1 models and 1 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 1 | 1.00 | 200.65 | — | 1.00 (1/1) | 1.00 | 0.00 | 81294/1379 | 15 | 4 |

## Per-Scenario Summary

1/1 passed, 0/1 agent-failed, 0/1 infra-error, 0/1 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1 | no data | — | — | — | — |
| k8s-1g | no data | — | — | — | — |
| k8s-2 | no data | — | — | — | — |
| k8s-2g | no data | — | — | — | — |
| k8s-3 | no data | — | — | — | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4 | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5 | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-2 | no data | — | — | — | — |
| os-2g | no data | — | — | — | — |
| os-3 | no data | — | — | — | — |
| os-3g | no data | — | — | — | — |
| cross-1 | 1 | success | 1.00 | 200.65 | — |
| cross-2 | no data | — | — | — | — |
| cross-3 | no data | — | — | — | — |
| boundary-1 | no data | — | — | — | — |
| boundary-2 | no data | — | — | — | — |
| boundary-3 | no data | — | — | — | — |
| boundary-4 | no data | — | — | — | — |
| deceptive-1 | no data | — | — | — | — |
| deceptive-2 | no data | — | — | — | — |
| ingress-1 | no data | — | — | — | — |
| pg-1 | no data | — | — | — | — |
| redis-1 | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| cross-1 | cross | — | N/A |

---

_Single-seed campaign — std values omitted._
