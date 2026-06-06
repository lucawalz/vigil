# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.54 | 172.73 | 62.85 | 0.64 (7/11) | 0.00 | 0.00 | — | 150360.36/6940.18 | 15.09 | 8.27 |

## Per-Scenario Summary

7/13 passed, 0/13 out-of-scope, 3/13 agent-failed, 2/13 infra-error, 1/13 gate-uncertain, 0/13 awaiting-review, 0/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 140.16 | — |
| k8s-2g | 1 | success | 1.00 | 221.65 | — |
| k8s-3g | 1 | success | 1.00 | 220.87 | — |
| k8s-4g | 1 | success | 1.00 | 222.73 | — |
| k8s-5g | 1 | success | 1.00 | 219.41 | — |
| k8s-rollback-1 | 1 | gate_failed | 0.00 | 1137.94 | — |
| os-1 | 1 | abort | 0.00 | — | — |
| os-1g | 1 | escalated | 0.00 | 619.14 | — |
| os-drift-sysctl | 1 | abort | 0.00 | — | — |
| os-stale-generation | 1 | escalated | 0.00 | 57.69 | — |
| deceptive-2 | 1 | flux_degraded | 0.00 | 629.52 | — |
| disk-pressure | 1 | escalated | 1.00 | 80.72 | — |
| live-quota-injected | 1 | escalated | 1.00 | 103.56 | — |

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
| os-1g | os | 0/1 | 0.00 |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | 0/1 | 0.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
