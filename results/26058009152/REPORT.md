# Phase 9 — Eval Campaign Aggregation Report

Total runs: 8 across 1 models and 8 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 8 | 0.25 | 277.43 | 37.26 | 1.00 (4/4) | 0.38 | 0.12 | 87105.25/1636.25 | 17.50 | 5.50 |

## Per-Scenario Summary

2/8 passed, 5/8 agent-failed, 0/8 infra-error, 1/8 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1 | 1 | gate_failed | 0.00 | 285.09 | — |
| k8s-2 | 1 | abort | 0.00 | — | — |
| k8s-3 | 1 | abort | 0.00 | — | — |
| k8s-4 | 1 | rollback_failed | 0.00 | 191.35 | — |
| k8s-5 | 1 | abort | 0.00 | — | — |
| os-1 | no data | — | — | — | — |
| os-2 | no data | — | — | — | — |
| os-3 | no data | — | — | — | — |
| cross-1 | 1 | success | 1.00 | 303.77 | — |
| cross-2 | 1 | abort | 0.00 | — | — |
| cross-3 | 1 | success | 1.00 | 251.08 | — |
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
| cross-1 | os | 1/1 | 1.00 |
| cross-2 | os | — | N/A |
| cross-3 | os | 1/1 | 1.00 |
| k8s-1 | k8s | — | N/A |
| k8s-2 | k8s | — | N/A |
| k8s-3 | k8s | — | N/A |
| k8s-4 | k8s | — | N/A |
| k8s-5 | k8s | — | N/A |

---

_Single-seed campaign — std values omitted._
