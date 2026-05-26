# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3-coder-next:cloud | 7 | 0.29 | 289.63 | 4.48 | 0.50 (3/6) | 0.43 | 0.14 | 71535.29/1092.29 | 10.71 | 5.57 |

## Per-Scenario Summary

3/12 passed, 2/12 out-of-scope, 1/12 agent-failed, 1/12 infra-error, 0/12 gate-uncertain, 5/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 286.46 | — |
| k8s-2g | 1 | rollback_succeeded | 0.00 | 223.37 | — |
| k8s-3g | 1 | setup_error | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 292.80 | — |
| k8s-5g | 1 | escalated | 0.00 | 9.67 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | success | 0.00 | 234.51 | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | success | 0.00 | 243.01 | — |

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
