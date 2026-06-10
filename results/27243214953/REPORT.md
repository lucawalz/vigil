# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.74 | 496.54 | 409.26 | 0.85 (29/34) | 0.00 | 0.05 | 1.00 | 225923/4520.65 | 18.94 | 6.97 |

## Per-Scenario Summary

29/39 runs passed, 5 agent-failed, 5 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
7/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 367 ± 46 | 3/3 | 10 | 16 |
| k8s-2g | 3/3 | OK OK OK | 515 ± 118 | 3/3 | 10 | 22 |
| k8s-3g | 3/3 | OK OK OK | 405 ± 26 | 3/3 | 10 | 16 |
| k8s-4g | 3/3 | OK OK OK | 433 ± 43 | 3/3 | 10 | 19 |
| k8s-5g | 3/3 | OK OK OK | 454 ± 65 | 3/3 | 10 | 20 |
| k8s-rollback-1 | 3/3 | RB OK RB | 1497 ± 746 | 3/3 | 13 | 36 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK OK TO | 298 ± 27 | 2/2 | 3 | 13 |
| os-1g | 2/3 | OK OK TO | 378 ± 24 | 2/2 | 7 | 13 |
| os-drift-sysctl | 2/3 | OK OK TO | 234 ± 54 | 2/2 | 3 | 9 |
| os-stale-generation | 1/3 | ESC OK TO | 289 | 1/2 | 2 | 13 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 11 |
| disk-pressure | 1/3 | ESC ESC TO | 389 | 1/2 | 1 | 11 |
| live-quota-injected | 3/3 | ESC ESC ESC | 296 ± 73 | 3/3 | 1 | 15 |

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
| os-1 | os | 2/2 | 1.00 |
| os-1g | os | 2/2 | 1.00 |
| os-drift-sysctl | os | 2/2 | 1.00 |
| os-stale-generation | os | 1/2 | 0.50 |
| disk-pressure | os | 1/2 | 0.50 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
