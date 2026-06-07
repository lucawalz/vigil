# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.92 | 195.33 | 137.38 | 0.92 (12/13) | 0.00 | 0.08 | 1.00 | 128075/5576.38 | 11.77 | 6.62 |

## Per-Scenario Summary

12/13 passed, 0/13 out-of-scope, 1/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 221.92 | — |
| k8s-2g | 1 | success | 1.00 | 223.22 | — |
| k8s-3g | 1 | success | 1.00 | 214.90 | — |
| k8s-4g | 1 | success | 1.00 | 219.95 | — |
| k8s-5g | 1 | success | 1.00 | 224.65 | — |
| k8s-rollback-1 | 1 | rollback_succeeded | 1.00 | 573.71 | — |
| os-1 | 1 | success | 1.00 | 205.12 | — |
| os-1g | 1 | success | 1.00 | 124.48 | — |
| os-drift-sysctl | 1 | success | 1.00 | 39.00 | — |
| os-stale-generation | 1 | success | 1.00 | 131.66 | — |
| deceptive-2 | 1 | escalated | 0.00 | 335.68 | — |
| disk-pressure | 1 | escalated | 1.00 | 115.13 | — |
| live-quota-injected | 1 | escalated | 1.00 | 50.23 | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| k8s-1g | k8s | — | N/A |
| k8s-2g | k8s | — | N/A |
| k8s-3g | k8s | — | N/A |
| k8s-4g | k8s | — | N/A |
| k8s-5g | k8s | — | N/A |
| live-quota-injected | k8s | — | N/A |
| deceptive-2 | k8s | — | N/A |
| k8s-rollback-1 | k8s | — | N/A |
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
