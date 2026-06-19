# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.77 | 381.67 | 104.10 | 0.81 (30/37) | 0.00 | 0.00 | — | 191754.32/3668.95 | 16.97 | 6.05 |

## Per-Scenario Summary

30/39 runs passed, 7 agent-failed, 2 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 339 ± 1 | 3/3 | 10 | 15 |
| k8s-2g | 3/3 | OK OK OK | 423 ± 88 | 3/3 | 10 | 19 |
| k8s-3g | 3/3 | OK OK OK | 416 ± 93 | 3/3 | 10 | 18 |
| k8s-4g | 3/3 | OK OK OK | 399 ± 55 | 3/3 | 10 | 17 |
| k8s-5g | 3/3 | OK OK OK | 382 ± 68 | 3/3 | 10 | 17 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 10 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 387 ± 98 | 3/3 | 4 | 21 |
| os-1g | 3/3 | OK OK OK | 454 ± 192 | 3/3 | 10 | 23 |
| os-drift-sysctl | 3/3 | OK OK OK | 283 ± 106 | 3/3 | 4 | 18 |
| os-stale-generation | 2/3 | OK TO OK | 478 ± 165 | 2/2 | 4 | 22 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC TO ESC | 240 | 1/2 | 1 | 16 |
| disk-pressure | 1/3 | ESC ESC ESC | 357 | 1/3 | 1 | 11 |
| live-quota-injected | 2/3 | ESC ESC ESC | 323 ± 132 | 2/3 | 1 | 17 |

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
| os-1 | os | 3/3 | 1.00 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 2/2 | 1.00 |
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
