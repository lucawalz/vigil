# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.77 | 215.64 | 142.73 | 0.77 (10/13) | 0.00 | 0.08 | 1.00 | 124539.54/5313.23 | 11.69 | 6.38 |

## Per-Scenario Summary

10/13 passed, 0/13 out-of-scope, 3/13 agent-failed, 0/13 infra-error, 0/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 222.49 | — |
| k8s-2g | 1 | success | 1.00 | 220.41 | — |
| k8s-3g | 1 | success | 1.00 | 281.25 | — |
| k8s-4g | 1 | success | 1.00 | 224.20 | — |
| k8s-5g | 1 | success | 1.00 | 223.28 | — |
| k8s-rollback-1 | 1 | rollback_succeeded | 1.00 | 552.27 | — |
| os-1 | 1 | escalated | 0.00 | 68.74 | — |
| os-1g | 1 | success | 1.00 | 153.24 | — |
| os-drift-sysctl | 1 | success | 1.00 | 46.37 | — |
| os-stale-generation | 1 | success | 1.00 | 197.98 | — |
| deceptive-2 | 1 | escalated | 0.00 | 319.18 | — |
| disk-pressure | 1 | escalated | 0.00 | 59.38 | — |
| live-quota-injected | 1 | escalated | 1.00 | 34.90 | — |

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
| os-1 | os | 0/1 | 0.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign — std values omitted._
