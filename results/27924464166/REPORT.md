# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.69 | 472.75 | 274.95 | 0.73 (27/37) | 0.23 | 0.10 | 1.00 | 281052.46/5284.76 | 21.54 | 8.65 |

## Per-Scenario Summary

29/39 runs passed, 8 agent-failed, 2 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
7/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 418 ± 39 | 3/3 | 10 | 15 |
| k8s-2g | 3/3 | OK OK OK | 577 ± 122 | 3/3 | 10 | 21 |
| k8s-3g | 3/3 | OK OK OK | 443 ± 97 | 3/3 | 10 | 19 |
| k8s-4g | 3/3 | OK OK OK | 406 ± 5 | 3/3 | 10 | 17 |
| k8s-5g | 3/3 | OK OK OK | 494 ± 132 | 3/3 | 10 | 17 |
| k8s-rollback-1 | 2/3 | RB TO RB | 1078 ± 282 | 2/2 | 11 | 20 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | OK KO KO | 141 | 1/3 | 6 | 20 |
| os-1g | 3/3 | OK OK OK | 346 ± 88 | 3/3 | 10 | 25 |
| os-drift-sysctl | 3/3 | OK OK OK | 206 ± 128 | 3/3 | 4 | 19 |
| os-stale-generation | 2/3 | KO OK OK | 300 ± 72 | 2/3 | 6 | 24 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO TO KO | — | 0/2 | 11 | 22 |
| disk-pressure | 0/3 | KO KO KO | — | 0/3 | 7 | 21 |
| live-quota-injected | 1/3 | ?? ESC ?? | 1197 | 1/3 | 8 | 37 |

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
| os-1 | os | 1/3 | 0.33 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
