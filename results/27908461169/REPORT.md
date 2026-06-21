# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.92 | 194.53 | 126.80 | 0.92 (12/13) | 0.00 | 0.08 | 1.00 | 128411.38/5680.54 | 12 | 6.38 |

## Per-Scenario Summary

12/13 runs passed, 1 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
12/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 218 | 1/1 | 10 | 12 |
| k8s-2g | 1/1 | OK | 195 | 1/1 | 10 | 15 |
| k8s-3g | 1/1 | OK | 198 | 1/1 | 10 | 15 |
| k8s-4g | 1/1 | OK | 221 | 1/1 | 10 | 13 |
| k8s-5g | 1/1 | OK | 227 | 1/1 | 10 | 11 |
| k8s-rollback-1 | 1/1 | RB | 552 | 1/1 | 11 | 14 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK | 146 | 1/1 | 4 | 17 |
| os-1g | 1/1 | OK | 192 | 1/1 | 10 | 15 |
| os-drift-sysctl | 0/1 | ESC | — | 0/1 | 1 | 8 |
| os-stale-generation | 1/1 | OK | 153 | 1/1 | 4 | 16 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/1 | ESC | 99 | 1/1 | 1 | 7 |
| disk-pressure | 1/1 | ESC | 51 | 1/1 | 1 | 6 |
| live-quota-injected | 1/1 | ESC | 81 | 1/1 | 1 | 7 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

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
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
