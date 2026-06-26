# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.67 | 485.70 | 450.54 | 0.79 (27/34) | 0.15 | 0.18 | 0.86 | 306505.32/6433.24 | 23.62 | 10.32 |

## Per-Scenario Summary

30/39 runs passed, 9 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
5/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 383 ± 139 | 3/3 | 10 | 16 |
| k8s-2g | 2/3 | OK OK KO | 395 ± 97 | 3/3 | 13 | 26 |
| k8s-3g | 3/3 | OK OK OK | 312 ± 87 | 3/3 | 10 | 21 |
| k8s-4g | 3/3 | OK OK OK | 321 ± 34 | 3/3 | 10 | 18 |
| k8s-5g | 3/3 | OK OK OK | 312 ± 94 | 3/3 | 10 | 18 |
| k8s-rollback-1 | 2/3 | ESC RB RB | 1901 ± 372 | 2/3 | 12 | 31 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK TO OK | 417 ± 14 | 2/2 | 3 | 13 |
| os-1g | 2/3 | OK TO OK | 462 ± 105 | 2/2 | 7 | 13 |
| os-drift-sysctl | 2/3 | OK TO OK | 200 ± 0 | 2/2 | 3 | 10 |
| os-stale-generation | 1/3 | KO TO OK | 273 | 1/2 | 5 | 15 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 19 | 45 |
| disk-pressure | 0/3 | KO TO ?? | — | 0/2 | 13 | 28 |
| live-quota-injected | 3/3 | ESC ESC ESC | 540 ± 387 | 3/3 | 3 | 14 |

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
