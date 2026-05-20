# Phase 9 — Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 13 | 0.08 | 350.59 | — | 0.50 (1/2) | 0.08 | 0.00 | 41618.57/462.14 | 5.86 | 0.71 |

## Per-Scenario Summary

1/13 passed, 7/13 agent-failed, 5/13 infra-error, 0/13 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1 | 1 | abort | 0.00 | — | — |
| k8s-1g | 1 | setup_error | 0.00 | — | — |
| k8s-2 | 1 | abort | 0.00 | — | — |
| k8s-2g | 1 | setup_error | 0.00 | — | — |
| k8s-3 | 1 | abort | 0.00 | — | — |
| k8s-3g | 1 | setup_error | 0.00 | — | — |
| k8s-4 | 1 | abort | 0.00 | — | — |
| k8s-4g | 1 | setup_error | 0.00 | — | — |
| k8s-5 | 1 | abort | 0.00 | — | — |
| k8s-5g | 1 | setup_error | 0.00 | — | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-2 | no data | — | — | — | — |
| os-2g | no data | — | — | — | — |
| os-3 | no data | — | — | — | — |
| os-3g | no data | — | — | — | — |
| cross-1 | 1 | abort | 0.00 | — | — |
| cross-2 | 1 | escalated | 0.00 | 227.69 | — |
| cross-3 | 1 | success | 1.00 | 350.59 | — |
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
| k8s-3 | k8s | — | N/A |
| k8s-4 | k8s | — | N/A |
| k8s-5 | k8s | — | N/A |
| k8s-1g | k8s | — | N/A |
| k8s-2g | k8s | — | N/A |
| k8s-3g | k8s | — | N/A |
| k8s-4g | k8s | — | N/A |
| k8s-5g | k8s | — | N/A |

---

_Single-seed campaign — std values omitted._
