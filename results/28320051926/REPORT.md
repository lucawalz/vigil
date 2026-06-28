# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.51 | 440.51 | 204.02 | 0.80 (20/25) | 0.13 | 0.08 | 1.00 | 296073.04/5117.88 | 22.60 | 9.12 |

## Per-Scenario Summary

21/39 runs passed, 17 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | OK OK TO | 371 ± 40 | 2/2 | 7 | 10 |
| k8s-2g | 2/3 | OK OK TO | 514 ± 101 | 2/2 | 7 | 17 |
| k8s-3g | 2/3 | OK OK TO | 569 ± 20 | 2/2 | 7 | 14 |
| k8s-4g | 2/3 | OK OK TO | 415 ± 27 | 2/2 | 7 | 11 |
| k8s-5g | 2/3 | OK OK TO | 443 ± 103 | 2/2 | 7 | 11 |
| k8s-rollback-1 | 2/3 | RB RB TO | 906 ± 120 | 2/2 | 8 | 16 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK OK TO | 266 ± 71 | 2/2 | 3 | 13 |
| os-1g | 2/3 | OK OK TO | 395 ± 147 | 2/2 | 7 | 15 |
| os-drift-sysctl | 2/3 | OK OK TO | 189 ± 72 | 2/2 | 3 | 13 |
| os-stale-generation | 1/3 | KO OK TO | 235 | 1/2 | 8 | 19 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO TO TO | — | 0/1 | 7 | 15 |
| disk-pressure | 0/3 | KO KO TO | — | 0/2 | 9 | 25 |
| live-quota-injected | 1/3 | ?? ESC TO | 436 | 1/2 | 4 | 17 |

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
| disk-pressure | os | 0/2 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
