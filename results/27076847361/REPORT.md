# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.69 | 256.77 | 182.73 | 0.69 (9/13) | 0.00 | 0.08 | 1.00 | 99082.38/5045 | 10.54 | 5.92 |

## Per-Scenario Summary

9/13 passed, 1/13 out-of-scope, 3/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 218.17 | — |
| k8s-2g | 1 | success | 1.00 | 280.29 | — |
| k8s-3g | 1 | success | 1.00 | 218.10 | — |
| k8s-4g | 1 | success | 1.00 | 217.48 | — |
| k8s-5g | 1 | success | 1.00 | 343.67 | — |
| k8s-rollback-1 | 1 | rollback_succeeded | 1.00 | 692.65 | — |
| os-1 | 1 | success | 1.00 | 152.79 | — |
| os-1g | 1 | success | 0.00 | 48.09 | — |
| os-drift-sysctl | 1 | escalated | 0.00 | 325.32 | — |
| os-stale-generation | 1 | success | 1.00 | 111.17 | — |
| deceptive-2 | 1 | escalated | 0.00 | 315.40 | — |
| disk-pressure | 1 | escalated | 1.00 | 76.57 | — |
| live-quota-injected | 1 | escalated | 0.00 | 8.24 | — |

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
| os-1g | os | 0/1 | 0.00 |
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
