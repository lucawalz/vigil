# Eval Campaign Aggregation Report

Total runs: 7 across 1 models and 7 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3-coder-next:cloud | 7 | 0.57 | 226.76 | 106.97 | 0.60 (3/5) | 0.43 | 0.00 | 71492.86/921.86 | 10.14 | 5.43 |

## Per-Scenario Summary

4/12 passed, 1/12 out-of-scope, 2/12 agent-failed, 0/12 infra-error, 0/12 gate-uncertain, 5/12 not-run

| Scenario | N | Outcome | Success Rate | Mean MTTR (s) | Std MTTR (s) |
|---|---:|---|---:|---:|---:|
| k8s-1g | 1 | success | 1.00 | 285.19 | — |
| k8s-2g | 1 | success | 1.00 | 271.82 | — |
| k8s-3g | 1 | inject_did_not_break | 0.00 | — | — |
| k8s-4g | 1 | success | 1.00 | 283.49 | — |
| k8s-5g | 1 | success | 0.00 | 139.20 | — |
| os-1 | no data | — | — | — | — |
| os-1g | no data | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — |
| os-stale-generation | no data | — | — | — | — |
| deceptive-2 | 1 | inject_did_not_break | 0.00 | — | — |
| disk-pressure | no data | — | — | — | — |
| live-quota-injected | 1 | escalated | 1.00 | 66.56 | — |

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
