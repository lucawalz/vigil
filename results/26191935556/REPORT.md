# Phase 9 — Eval Campaign Aggregation Report

Total runs: 5 across 1 models and 5 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 5 | 0.20 | 552.67 | — | 0.00 (0/2) | 0.40 | 0.20 | 110499.50/2958.50 | 19 | 9 |

## Per-Scenario Summary

1/5 passed, 4/5 agent-failed, 0/5 infra-error, 0/5 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1 | 1 | success | 1.00 | 552.67 | — |
| k8s-1g | no data | — | — | — | — |
| k8s-2 | 1 | rollback_failed | 0.00 | 381.48 | — |
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
| cross-1 | 1 | abort | 0.00 | — | — |
| cross-2 | 1 | abort | 0.00 | — | — |
| cross-3 | 1 | abort | 0.00 | — | — |
| boundary-1 | no data | — | — | — | — |
| boundary-2 | no data | — | — | — | — |
| boundary-3 | no data | — | — | — | — |
| boundary-4 | no data | — | — | — | — |
| ingress-1 | no data | — | — | — | — |
| pg-1 | no data | — | — | — | — |
| redis-1 | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| cross-1 | cross | — | N/A |
| cross-2 | cross | — | N/A |
| cross-3 | cross | — | N/A |
| k8s-1 | k8s | — | N/A |
| k8s-2 | k8s | — | N/A |

---

_Single-seed campaign — std values omitted._
