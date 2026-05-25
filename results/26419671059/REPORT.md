# Eval Campaign Aggregation Report

Total runs: 1 across 1 models and 1 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3-coder-next:cloud | 1 | 0.00 | — | — | — | 0.00 | 0.00 | 0/0 | 0 | 0 |

## Per-Scenario Summary

0/12 passed, 0/12 out-of-scope, 1/12 agent-failed, 0/12 infra-error, 0/12 gate-uncertain, 11/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | escalated | 0.00 | 0.87 | — |
| k8s-2g | no data | — | — | — | — |
| k8s-3g | no data | — | — | — | — |
| k8s-4g | no data | — | — | — | — |
| k8s-5g | no data | — | — | — | — |
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

---

_Single-seed campaign — std values omitted._
