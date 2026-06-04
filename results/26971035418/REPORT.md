# Eval Campaign Aggregation Report

Total runs: 13 across 2 models and 9 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 8 | 0.50 | 546.15 | 19.26 | 0.83 (5/6) | 0.00 | 0.12 | 0.00 | 150234/4392.33 | 19.83 | 10.50 |
| qwen3-coder-next:cloud | 5 | 0.00 | — | — | — | 0.00 | 0.00 | — | 0/0 | 0 | 0 |

## Per-Scenario Summary

4/13 passed, 0/13 out-of-scope, 1/13 agent-failed, 3/13 infra-error, 1/13 gate-uncertain, 0/13 awaiting-review, 4/13 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 527.74 | — |
| k8s-2g | 1 | success | 1.00 | 565.12 | — |
| k8s-3g | 1 | abort | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 560.26 | — |
| k8s-5g | 1 | success | 1.00 | 531.49 | — |
| k8s-rollback-1 | 1 | gate_failed | 0.00 | 295.15 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | rollback_failed | 0.00 | 523.14 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | abort | 0.00 | — | — |

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| k8s-1g | k8s | — | N/A |
| k8s-1 | None | — | N/A |
| k8s-2g | k8s | — | N/A |
| k8s-3g | k8s | — | N/A |
| k8s-4g | k8s | — | N/A |
| k8s-5g | k8s | — | N/A |
| live-quota-injected | k8s | — | N/A |
| deceptive-2 | k8s | — | N/A |
| k8s-rollback-1 | k8s | — | N/A |

---

_Note: std values computed from 5 seeds per cell; treat as directional only._
