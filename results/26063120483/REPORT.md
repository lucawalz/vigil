# Phase 9 — Eval Campaign Aggregation Report

Total runs: 3 across 1 models and 3 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 3 | 1.00 | 310.77 | 73.85 | 1.00 (3/3) | 1.00 | 0.00 | 151026.33/1826.67 | 24 | 5 |

## Per-Scenario Summary

3/3 passed, 0/3 agent-failed, 0/3 infra-error, 0/3 gate-uncertain

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
| cross-1 | 1 | success | 1.00 | 363.57 | — |
| cross-2 | 1 | success | 1.00 | 226.38 | — |
| cross-3 | 1 | success | 1.00 | 342.36 | — |
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
| cross-2 | os | 1/1 | 1.00 |
| cross-3 | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
