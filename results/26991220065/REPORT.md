# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.54 | 177.57 | 78.96 | 0.67 (6/9) | 0.08 | 0.08 | 0.00 | 85708.11/4564.89 | 11.78 | 7.44 |

## Per-Scenario Summary

7/13 passed, 0/13 out-of-scope, 2/13 agent-failed, 4/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 218.80 | — |
| k8s-2g | 1 | success | 1.00 | 223.23 | — |
| k8s-3g | 1 | success | 1.00 | 220.31 | — |
| k8s-4g | 1 | success | 1.00 | 220.24 | — |
| k8s-5g | 1 | success | 1.00 | 220.62 | — |
| k8s-rollback-1 | 1 | escalated | 0.00 | 122.37 | — |
| os-1 | 1 | abort | 0.00 | — | — |
| os-1g | 1 | abort | 0.00 | — | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | abort | 0.00 | — | — |
| deceptive-2 | 1 | rollback_failed | 0.00 | 1571.95 | — |
| disk-pressure | 1 | escalated | 1.00 | 119.60 | — |
| live-quota-injected | 1 | escalated | 1.00 | 20.20 | — |

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
| os-1 | os | — | N/A |
| os-1g | os | — | N/A |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | — | N/A |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
