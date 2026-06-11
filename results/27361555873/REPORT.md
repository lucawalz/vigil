# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.77 | 483.90 | 248.50 | 0.77 (30/39) | 0.00 | 0.05 | 1.00 | 214862.79/3960.10 | 17.64 | 6.21 |

## Per-Scenario Summary

30/39 runs passed, 9 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 432 ± 50 | 3/3 | 10 | 16 |
| k8s-2g | 3/3 | OK OK OK | 544 ± 32 | 3/3 | 10 | 21 |
| k8s-3g | 3/3 | OK OK OK | 472 ± 100 | 3/3 | 10 | 20 |
| k8s-4g | 3/3 | OK OK OK | 499 ± 69 | 3/3 | 10 | 19 |
| k8s-5g | 3/3 | OK OK OK | 524 ± 67 | 3/3 | 10 | 19 |
| k8s-rollback-1 | 2/3 | ESC RB RB | 1284 ± 92 | 2/3 | 8 | 23 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | OK ESC ESC | 374 | 1/3 | 2 | 20 |
| os-1g | 3/3 | OK OK OK | 443 ± 86 | 3/3 | 10 | 21 |
| os-drift-sysctl | 3/3 | OK OK OK | 186 ± 45 | 3/3 | 4 | 12 |
| os-stale-generation | 3/3 | OK OK OK | 353 ± 60 | 3/3 | 4 | 18 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 11 |
| disk-pressure | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 13 |
| live-quota-injected | 3/3 | ESC ESC ESC | 406 ± 162 | 3/3 | 1 | 16 |

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
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
