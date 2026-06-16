# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.82 | 428.32 | 196.49 | 0.87 (33/38) | 0.00 | 0.03 | 1.00 | 223528.66/4078.79 | 18.39 | 6.21 |

## Per-Scenario Summary

32/39 runs passed, 7 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | ?? OK OK | 436 ± 37 | 3/3 | 11 | 15 |
| k8s-2g | 3/3 | OK OK OK | 601 ± 25 | 3/3 | 10 | 22 |
| k8s-3g | 3/3 | OK OK OK | 457 ± 66 | 3/3 | 10 | 20 |
| k8s-4g | 3/3 | OK OK OK | 522 ± 104 | 3/3 | 10 | 20 |
| k8s-5g | 3/3 | OK OK OK | 415 ± 47 | 3/3 | 10 | 17 |
| k8s-rollback-1 | 1/3 | RB ESC ESC | 1285 | 1/3 | 4 | 21 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK TO OK | 355 ± 23 | 2/2 | 3 | 21 |
| os-1g | 3/3 | OK OK OK | 388 ± 89 | 3/3 | 10 | 22 |
| os-drift-sysctl | 3/3 | OK OK OK | 193 ± 58 | 3/3 | 4 | 15 |
| os-stale-generation | 3/3 | OK OK OK | 323 ± 74 | 3/3 | 4 | 21 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC ESC ESC | 484 | 1/3 | 1 | 15 |
| disk-pressure | 2/3 | ESC ESC ESC | 369 ± 40 | 2/3 | 1 | 15 |
| live-quota-injected | 3/3 | ESC ESC ESC | 306 ± 12 | 3/3 | 1 | 15 |

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
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
