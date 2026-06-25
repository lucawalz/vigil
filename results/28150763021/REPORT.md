# Eval Campaign Aggregation Report

Total runs: 12 across 1 models and 12 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 12 | 0.67 | 310.70 | 123.52 | 0.80 (8/10) | 0.08 | 0.00 | — | 257484.80/4756.10 | 21.40 | 7.60 |

## Per-Scenario Summary

8/12 runs passed, 3 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 27 not-run
8/12 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 217 | 1/1 | 11 | 16 |
| k8s-2g | 1/1 | OK | 572 | 1/1 | 15 | 32 |
| k8s-3g | 0/1 | TO | — | — | 1 | 3 |
| k8s-4g | 1/1 | OK | 215 | 1/1 | 10 | 15 |
| k8s-5g | 1/1 | OK | 346 | 1/1 | 11 | 22 |
| k8s-rollback-1 | 0/1 | TO | — | — | 3 | 17 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK | 305 | 1/1 | 4 | 22 |
| os-1g | 0/1 | KO | — | 0/1 | 4 | 21 |
| os-drift-sysctl | 1/1 | OK | 213 | 1/1 | 4 | 23 |
| os-stale-generation | 1/1 | OK | 238 | 1/1 | 4 | 21 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/1 | ?? | — | 0/1 | 12 | 23 |
| disk-pressure | no data | — | — | — | — | — |
| live-quota-injected | 1/1 | ESC | 380 | 1/1 | 1 | 19 |

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
| os-1g | os | 0/1 | 0.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |

---

_Single-seed campaign - std values omitted._
