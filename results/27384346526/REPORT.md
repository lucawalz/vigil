# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.74 | 427.72 | 178.11 | 0.79 (30/38) | 0.00 | 0.05 | 1.00 | 222656.74/4035.29 | 18.05 | 6.26 |

## Per-Scenario Summary

30/39 runs passed, 8 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 391 ± 131 | 3/3 | 10 | 15 |
| k8s-2g | 2/3 | OK KO OK | 585 ± 77 | 3/3 | 11 | 24 |
| k8s-3g | 3/3 | OK OK OK | 452 ± 14 | 3/3 | 10 | 19 |
| k8s-4g | 3/3 | OK OK OK | 419 ± 23 | 3/3 | 10 | 18 |
| k8s-5g | 3/3 | OK OK OK | 435 ± 41 | 3/3 | 10 | 19 |
| k8s-rollback-1 | 1/3 | TO RB ESC | 1181 | 1/2 | 7 | 19 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK OK ESC | 392 ± 7 | 2/3 | 3 | 19 |
| os-1g | 3/3 | OK OK OK | 477 ± 67 | 3/3 | 10 | 24 |
| os-drift-sysctl | 3/3 | OK OK OK | 255 ± 49 | 3/3 | 4 | 17 |
| os-stale-generation | 3/3 | OK OK OK | 290 ± 30 | 3/3 | 4 | 21 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 9 |
| disk-pressure | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 20 |
| live-quota-injected | 3/3 | ESC ESC ESC | 372 ± 138 | 3/3 | 1 | 15 |

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
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
