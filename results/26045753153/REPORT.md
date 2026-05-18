# Phase 9 — Eval Campaign Aggregation Report

Total runs: 9 across 1 models and 9 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 9 | 0.00 | — | — | — | 0.00 | 0.00 | 0/0 | 0 | 0 |

## Per-Scenario Summary

0/9 passed, 0/9 agent-failed, 9/9 infra-error, 0/9 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1 | no data | — | — | — | — |
| k8s-2 | no data | — | — | — | — |
| k8s-3 | no data | — | — | — | — |
| k8s-4 | no data | — | — | — | — |
| k8s-5 | no data | — | — | — | — |
| os-1 | 1 | baseline_degraded | 0.00 | — | — |
| os-2 | 1 | baseline_degraded | 0.00 | — | — |
| os-3 | 1 | baseline_degraded | 0.00 | — | — |
| cross-1 | 1 | baseline_degraded | 0.00 | — | — |
| cross-2 | 1 | baseline_degraded | 0.00 | — | — |
| cross-3 | 1 | baseline_degraded | 0.00 | — | — |
| boundary-1 | 1 | baseline_degraded | 0.00 | — | — |
| boundary-2 | 1 | baseline_degraded | 0.00 | — | — |
| boundary-3 | 1 | baseline_degraded | 0.00 | — | — |
| boundary-4 | no data | — | — | — | — |
| ingress-1 | no data | — | — | — | — |
| pg-1 | no data | — | — | — | — |
| redis-1 | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| cross-1 | os | — | N/A |
| cross-2 | os | — | N/A |
| cross-3 | os | — | N/A |
| boundary-1 | k8s | — | N/A |
| boundary-2 | k8s | — | N/A |
| boundary-3 | k8s | — | N/A |
| os-1 | os | — | N/A |
| os-2 | os | — | N/A |
| os-3 | os | — | N/A |

---

_Single-seed campaign — std values omitted._
