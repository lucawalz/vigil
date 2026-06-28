# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.26 | 533.14 | 298.75 | 0.83 (10/12) | 0.05 | 0.03 | 0.00 | 304904.38/5688.31 | 22.54 | 9 |

## Per-Scenario Summary

10/39 runs passed, 27 agent-failed, 2 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/3 | OK TO TO | 344 | 1/1 | 4 | 4 |
| k8s-2g | 1/3 | OK TO TO | 399 | 1/1 | 4 | 7 |
| k8s-3g | 1/3 | OK TO TO | 691 | 1/1 | 4 | 6 |
| k8s-4g | 1/3 | OK TO TO | 396 | 1/1 | 4 | 6 |
| k8s-5g | 1/3 | OK TO TO | 403 | 1/1 | 4 | 6 |
| k8s-rollback-1 | 0/3 | TO TO TO | — | — | 5 | 14 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | OK TO TO | 323 | 1/1 | 2 | 4 |
| os-1g | 1/3 | OK TO ?? | 558 | 1/1 | 6 | 14 |
| os-drift-sysctl | 1/3 | OK TO TO | 571 | 1/1 | 2 | 5 |
| os-stale-generation | 0/3 | ?? TO TO | — | 0/1 | 10 | 25 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC TO TO | 336 | 1/1 | 1 | 3 |
| disk-pressure | 0/3 | KO TO TO | — | 0/1 | 5 | 16 |
| live-quota-injected | 1/3 | ESC TO TO | 1310 | 1/1 | 3 | 6 |

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
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 0/1 | 0.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
