# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.79 | 475.07 | 296.21 | 0.84 (31/37) | 0.13 | 0.10 | 1.00 | 312119.78/5598.27 | 23.35 | 9.08 |

## Per-Scenario Summary

34/39 runs passed, 4 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
10/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 412 ± 50 | 3/3 | 10 | 16 |
| k8s-2g | 3/3 | OK OK OK | 504 ± 123 | 3/3 | 10 | 23 |
| k8s-3g | 3/3 | OK OK OK | 399 ± 120 | 3/3 | 10 | 16 |
| k8s-4g | 3/3 | OK OK OK | 387 ± 79 | 3/3 | 10 | 19 |
| k8s-5g | 3/3 | OK OK OK | 342 ± 59 | 3/3 | 10 | 18 |
| k8s-rollback-1 | 1/3 | RB ESC TO | 1600 | 1/2 | 9 | 24 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 324 ± 103 | 3/3 | 4 | 20 |
| os-1g | 3/3 | OK OK OK | 348 ± 87 | 3/3 | 10 | 22 |
| os-drift-sysctl | 3/3 | OK OK OK | 258 ± 49 | 3/3 | 4 | 19 |
| os-stale-generation | 3/3 | OK OK OK | 731 ± 420 | 3/3 | 8 | 35 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 24 | 52 |
| disk-pressure | 0/3 | KO KO TO | — | 0/2 | 3 | 19 |
| live-quota-injected | 3/3 | ESC ESC ESC | 672 ± 325 | 3/3 | 3 | 18 |

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
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 0/2 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
