# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.56 | 455.46 | 374.12 | 0.76 (22/29) | 0.18 | 0.10 | 1.00 | 339661.17/5613.90 | 24.45 | 9.03 |

## Per-Scenario Summary

24/39 runs passed, 14 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
2/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | OK TO OK | 406 ± 90 | 2/2 | 7 | 11 |
| k8s-2g | 2/3 | OK TO OK | 331 ± 19 | 2/2 | 7 | 16 |
| k8s-3g | 2/3 | OK TO OK | 322 ± 109 | 2/2 | 7 | 11 |
| k8s-4g | 2/3 | OK TO OK | 416 ± 233 | 2/2 | 7 | 12 |
| k8s-5g | 2/3 | OK TO OK | 349 ± 4 | 2/2 | 7 | 11 |
| k8s-rollback-1 | 2/3 | RB TO RB | 1394 ± 577 | 2/2 | 9 | 25 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/3 | KO TO KO | — | 0/2 | 12 | 40 |
| os-1g | 3/3 | OK OK OK | 246 ± 73 | 3/3 | 10 | 21 |
| os-drift-sysctl | 3/3 | OK OK OK | 228 ± 101 | 3/3 | 5 | 16 |
| os-stale-generation | 2/3 | OK OK KO | 435 ± 332 | 2/3 | 10 | 37 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | TO TO KO | — | 0/1 | 6 | 7 |
| disk-pressure | 0/3 | KO KO KO | — | 0/3 | 4 | 19 |
| live-quota-injected | 2/3 | ESC TO ESC | 646 ± 412 | 2/2 | 2 | 13 |

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
| os-1 | os | 0/2 | 0.00 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
