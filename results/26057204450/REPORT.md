# Phase 9 — Eval Campaign Aggregation Report

Total runs: 1 across 1 models and 1 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 1 | 0.00 | — | — | — | 0.00 | 0.00 | —/— | — | — |

## Per-Scenario Summary

0/1 passed, 1/1 agent-failed, 0/1 infra-error, 0/1 gate-uncertain

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1 | no data | — | — | — | — |
| k8s-2 | no data | — | — | — | — |
| k8s-3 | no data | — | — | — | — |
| k8s-4 | no data | — | — | — | — |
| k8s-5 | no data | — | — | — | — |
| os-1 | no data | — | — | — | — |
| os-2 | no data | — | — | — | — |
| os-3 | no data | — | — | — | — |
| cross-1 | 1 | abort | 0.00 | — | — |
| cross-2 | no data | — | — | — | — |
| cross-3 | no data | — | — | — | — |
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
| cross-1 | os | — | N/A |

---

_Single-seed campaign — std values omitted._
