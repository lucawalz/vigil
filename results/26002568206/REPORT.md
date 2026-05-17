# Phase 9 — Eval Campaign Aggregation Report

Total runs: 16 across 1 models and 16 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 16 | 0.06 | 139.96 | — | 1.00 (1/1) | 0.06 | 0.00 | 3172.27/79.13 | 0.93 | 1.20 |

## Per-Scenario Summary

| Scenario | N | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---:|---:|---:|
| k8s-1 | 1 | 0.00 | — | — |
| k8s-2 | 1 | 0.00 | — | — |
| k8s-3 | 1 | 0.00 | — | — |
| k8s-4 | 1 | 0.00 | — | — |
| k8s-5 | 1 | 0.00 | — | — |
| os-1 | 1 | 1.00 | 139.96 | — |
| os-2 | 1 | 0.00 | — | — |
| os-3 | no data | — | — | — |
| cross-1 | 1 | 0.00 | — | — |
| cross-2 | 1 | 0.00 | — | — |
| cross-3 | 1 | 0.00 | — | — |
| boundary-1 | 1 | 0.00 | — | — |
| boundary-2 | 1 | 0.00 | — | — |
| boundary-3 | 1 | 0.00 | — | — |
| boundary-4 | 1 | 0.00 | — | — |
| ingress-1 | 1 | 0.00 | — | — |
| pg-1 | no data | — | — | — |
| redis-1 | 1 | 0.00 | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| cross-1 | os | — | N/A |
| cross-2 | os | — | N/A |
| cross-3 | os | — | N/A |
| k8s-1 | k8s | — | N/A |
| k8s-2 | k8s | — | N/A |
| k8s-3 | k8s | — | N/A |
| k8s-4 | k8s | — | N/A |
| k8s-5 | k8s | — | N/A |
| boundary-1 | k8s | — | N/A |
| boundary-2 | k8s | — | N/A |
| boundary-3 | k8s | — | N/A |
| boundary-4 | k8s | — | N/A |
| redis-1 | k8s | — | N/A |
| ingress-1 | k8s | — | N/A |
| os-1 | os | 1/1 | 1.00 |
| os-2 | os | — | N/A |

---

_Single-seed campaign — std values omitted._
