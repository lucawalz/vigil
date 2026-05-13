# Phase 9 — Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| qwen3-coder-next:cloud | 7 | 0.43 | 157.24 | 22.07 | 0.60 | 0.57 | 0.00 | 61532/1526 | 14.71 |

## Per-Scenario Summary

| Scenario | N | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---:|---:|---:|
| cross-1 | 1 | 1.00 | 164.54 | — |
| cross-3 | 1 | 0.00 | 186.04 | — |
| k8s-1 | 1 | 0.00 | — | — |
| k8s-2 | 1 | 1.00 | 140.60 | — |
| k8s-3 | 1 | 0.00 | — | — |
| k8s-4 | 1 | 1.00 | 164.82 | — |
| k8s-5 | 1 | 0.00 | 130.21 | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| cross-1 | os | 1/1 | 1.00 |
| cross-3 | os | 0/1 | 0.00 |
| k8s-1 | k8s | — | N/A |
| k8s-2 | k8s | — | N/A |
| k8s-3 | k8s | — | N/A |
| k8s-4 | k8s | — | N/A |
| k8s-5 | k8s | — | N/A |

---

_Note: std values computed from 3 seeds per cell are approximate (n=3); treat as directional only._
