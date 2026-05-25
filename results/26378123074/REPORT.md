# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3-coder-next:cloud | 7 | 0.71 | 229.26 | 113.38 | 0.57 (4/7) | 0.57 | 0.00 | 85288.43/1362.43 | 15.14 | 7 |

## Per-Scenario Summary

5/12 passed, 1/12 out-of-scope, 1/12 agent-failed, 0/12 infra-error, 0/12 gate-uncertain, 5/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 278.00 | — |
| k8s-2g | 1 | escalated | 0.00 | 20.96 | — |
| k8s-3g | 1 | success | 1.00 | 276.28 | — |
| k8s-4g | 1 | success | 1.00 | 259.93 | — |
| k8s-5g | 1 | success | 1.00 | 303.71 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | success | 0.00 | 239.39 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 28.37 | — |

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

---

_Single-seed campaign — std values omitted._
