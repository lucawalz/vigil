# Phase 9 — Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| qwen3-coder-next:cloud | 13 | 0.38 | 159.76 | 23.12 | 0.90 | 0.31 | 0.00 | 62939.15/1234.38 | 17 |

## Per-Scenario Summary

| Scenario | N | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---:|---:|---:|
| cross-1 | 1 | 0.00 | — | — |
| cross-3 | 1 | 1.00 | 173.90 | — |
| k8s-1 | 1 | 1.00 | 130.58 | — |
| k8s-2 | 1 | 1.00 | 131.25 | — |
| k8s-3 | 1 | 0.00 | — | — |
| k8s-4 | 1 | 0.00 | 154.33 | — |
| k8s-5 | 1 | 0.00 | 148.10 | — |
| boundary-1 | 1 | 0.00 | — | — |
| boundary-2 | 1 | 0.00 | 159.33 | — |
| ingress-1 | 1 | 0.00 | 138.37 | — |
| os-1 | 1 | 1.00 | 193.37 | — |
| os-2 | 1 | 1.00 | 183.56 | — |
| os-3 | 1 | 0.00 | 184.77 | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| cross-1 | os | — | N/A |
| cross-3 | os | 1/1 | 1.00 |
| k8s-1 | k8s | — | N/A |
| k8s-2 | k8s | — | N/A |
| k8s-3 | k8s | — | N/A |
| k8s-4 | k8s | — | N/A |
| k8s-5 | k8s | — | N/A |
| boundary-1 | k8s | — | N/A |
| boundary-2 | k8s | — | N/A |
| ingress-1 | k8s | — | N/A |
| os-1 | os | 1/1 | 1.00 |
| os-2 | os | 1/1 | 1.00 |
| os-3 | os | 1/1 | 1.00 |

---

_Note: std values computed from 3 seeds per cell are approximate (n=3); treat as directional only._
