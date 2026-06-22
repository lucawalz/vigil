# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.69 | 459.57 | 359.62 | 0.69 (27/39) | 0.21 | 0.13 | 1.00 | 303407.54/5794.90 | 22.51 | 8.79 |

## Per-Scenario Summary

30/39 runs passed, 9 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
7/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 322 ± 33 | 3/3 | 10 | 16 |
| k8s-2g | 3/3 | OK OK OK | 334 ± 114 | 3/3 | 10 | 20 |
| k8s-3g | 3/3 | OK OK OK | 553 ± 439 | 3/3 | 13 | 26 |
| k8s-4g | 3/3 | OK OK OK | 310 ± 79 | 3/3 | 10 | 19 |
| k8s-5g | 3/3 | OK OK OK | 324 ± 66 | 3/3 | 10 | 17 |
| k8s-rollback-1 | 2/3 | RB ESC RB | 1371 ± 356 | 2/3 | 10 | 33 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK KO OK | 222 ± 85 | 2/3 | 6 | 22 |
| os-1g | 1/3 | KO OK KO | 520 | 1/3 | 6 | 22 |
| os-drift-sysctl | 3/3 | OK OK OK | 178 ± 41 | 3/3 | 4 | 20 |
| os-stale-generation | 1/3 | OK KO KO | 209 | 1/3 | 6 | 22 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 17 | 41 |
| disk-pressure | 0/3 | KO KO KO | — | 0/3 | 6 | 17 |
| live-quota-injected | 3/3 | ESC ESC ESC | 810 ± 211 | 3/3 | 4 | 18 |

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
| os-1 | os | 2/3 | 0.67 |
| os-1g | os | 1/3 | 0.33 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 1/3 | 0.33 |
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
