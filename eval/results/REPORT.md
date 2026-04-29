# Eval Campaign Aggregation Report

Total runs: 71 across 2 models and 12 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| qwen3-coder-next:cloud | 35 | 0.17 | 158.00 | 78.13 | 1.00 | 0.17 | 0.06 | 15853.43/979.20 | 6.03 |
| deepseek-v3.2:cloud | 36 | 0.11 | 168.22 | 26.85 | 0.40 | 0.14 | 0.03 | 8250.86/705.78 | 2.25 |

## Per-Scenario Summary

| Scenario | N | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---:|---:|---:|
| boundary-1 | 6 | 0.17 | 159.17 | — |
| cross-1 | 6 | 0.17 | 188.63 | — |
| cross-2 | 5 | 0.00 | — | — |
| cross-3 | 6 | 0.17 | 324.11 | — |
| k8s-1 | 6 | 0.33 | 180.68 | 40.86 |
| k8s-2 | 6 | 0.17 | 73.21 | 65.57 |
| k8s-3 | 6 | 0.17 | 174.38 | — |
| k8s-4 | 6 | 0.33 | 156.72 | 26.06 |
| k8s-5 | 6 | 0.00 | — | — |
| os-1 | 6 | 0.17 | 140.87 | — |
| os-2 | 6 | 0.00 | — | — |
| os-3 | 6 | 0.00 | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| boundary-1 | k8s | — | N/A |
| cross-1 | os | 1/1 | 1.00 |
| cross-2 | os | — | N/A |
| cross-3 | os | 1/1 | 1.00 |
| k8s-1 | k8s | — | N/A |
| k8s-2 | k8s | — | N/A |
| k8s-3 | k8s | — | N/A |
| k8s-4 | k8s | — | N/A |
| k8s-5 | k8s | — | N/A |
| os-1 | os | 1/1 | 1.00 |
| os-2 | os | — | N/A |
| os-3 | os | — | N/A |

---

_Note: std values computed from 3 seeds per cell are approximate (n=3); treat as directional only._
