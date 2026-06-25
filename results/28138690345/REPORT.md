# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.18 | 390.48 | 112.79 | 0.67 (8/12) | 0.05 | 0.05 | 1.00 | 307423/5251.17 | 21.42 | 6.83 |

## Per-Scenario Summary

9/39 runs passed, 29 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/3 | OK TO TO | 404 | 1/1 | 4 | 6 |
| k8s-2g | 1/3 | OK TO TO | 463 | 1/1 | 4 | 7 |
| k8s-3g | 1/3 | OK TO TO | 399 | 1/1 | 4 | 7 |
| k8s-4g | 0/3 | TO TO TO | — | — | 1 | 0 |
| k8s-5g | 1/3 | OK TO TO | 462 | 1/1 | 4 | 6 |
| k8s-rollback-1 | 0/3 | ESC TO TO | — | 0/1 | 1 | 5 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/3 | ESC TO TO | — | 0/1 | 1 | 7 |
| os-1g | 0/3 | KO TO TO | — | 1/1 | 5 | 8 |
| os-drift-sysctl | 1/3 | OK TO TO | 220 | 1/1 | 2 | 5 |
| os-stale-generation | 1/3 | OK TO TO | 257 | 1/1 | 2 | 7 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO TO TO | — | 0/1 | 5 | 17 |
| disk-pressure | 0/3 | KO TO TO | — | 0/1 | 2 | 7 |
| live-quota-injected | 1/3 | ESC TO TO | 528 | 1/1 | 1 | 5 |

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
| os-1 | os | 0/1 | 0.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
