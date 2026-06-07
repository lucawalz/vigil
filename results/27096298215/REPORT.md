# Eval Campaign Aggregation Report

Total runs: 2 across 1 models and 2 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 2 | 0.50 | 278.74 | — | 1.00 (2/2) | 0.00 | 0.50 | 1.00 | 229874.50/13033 | 32.50 | 20 |

## Per-Scenario Summary

2/13 passed, 0/13 out-of-scope, 0/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 11/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 278.74 | — |
| k8s-2g | 1 | rollback_succeeded | 0.00 | 1359.73 | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
| k8s-rollback-1 | no data | — | — | — | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | no data | — | — | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | no data | — | — | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| k8s-1g | k8s | — | N/A |
| k8s-2g | k8s | — | N/A |

---

_Single-seed campaign — std values omitted._
