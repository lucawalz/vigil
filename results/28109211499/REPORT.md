# Eval Campaign Aggregation Report

Total runs: 34 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 34 | 0.79 | 561.59 | 384.75 | 0.82 (27/33) | 0.18 | 0.21 | 0.86 | 316061.58/6036 | 24.27 | 10.64 |

## Per-Scenario Summary

30/34 runs passed, 3 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 5 not-run
10/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 381 ± 30 | 3/3 | 10 | 16 |
| k8s-2g | 3/3 | OK OK OK | 566 ± 121 | 3/3 | 10 | 21 |
| k8s-3g | 3/3 | OK OK OK | 419 ± 36 | 3/3 | 10 | 18 |
| k8s-4g | 3/3 | OK OK OK | 425 ± 75 | 3/3 | 10 | 17 |
| k8s-5g | 3/3 | OK OK OK | 492 ± 192 | 3/3 | 10 | 18 |
| k8s-rollback-1 | 3/3 | RB RB RB | 1407 ± 283 | 3/3 | 13 | 33 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/2 | OK OK — | 310 ± 8 | 2/2 | 4 | 22 |
| os-1g | 2/2 | OK OK — | 370 ± 65 | 2/2 | 10 | 22 |
| os-drift-sysctl | 2/2 | OK OK — | 242 ± 8 | 2/2 | 4 | 18 |
| os-stale-generation | 0/2 | ?? TO — | — | 0/1 | 19 | 65 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 24 | 48 |
| disk-pressure | 0/2 | KO KO — | — | 0/2 | 6 | 22 |
| live-quota-injected | 3/3 | ESC ESC ESC | 749 ± 585 | 3/3 | 4 | 11 |

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
| os-stale-generation | os | 0/1 | 0.00 |
| disk-pressure | os | 0/2 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
