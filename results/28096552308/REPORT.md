# Eval Campaign Aggregation Report

Total runs: 15 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 15 | 0.93 | 485.19 | 252.67 | 0.93 (14/15) | 0.07 | 0.13 | 1.00 | 273894.47/5007.33 | 21.07 | 8.80 |

## Per-Scenario Summary

15/15 runs passed, 0 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 24 not-run
12/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/2 | OK OK | 414 ± 26 | 2/2 | 10 | 14 |
| k8s-2g | 2/2 | OK OK | 462 ± 78 | 2/2 | 10 | 19 |
| k8s-3g | 1/1 | OK — | 412 | 1/1 | 10 | 16 |
| k8s-4g | 1/1 | OK — | 278 | 1/1 | 10 | 15 |
| k8s-5g | 1/1 | OK — | 350 | 1/1 | 10 | 17 |
| k8s-rollback-1 | 1/1 | RB — | 1197 | 1/1 | 11 | 22 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK — | 577 | 1/1 | 4 | 23 |
| os-1g | 1/1 | OK — | 485 | 1/1 | 10 | 25 |
| os-drift-sysctl | 1/1 | OK — | 238 | 1/1 | 4 | 16 |
| os-stale-generation | 1/1 | OK — | 321 | 1/1 | 4 | 19 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/1 | KO — | — | 0/1 | 23 | 64 |
| disk-pressure | 1/1 | ESC — | 836 | 1/1 | 5 | 15 |
| live-quota-injected | 1/1 | ESC — | 347 | 1/1 | 1 | 17 |

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
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Note: std values computed from 2 seeds per cell; treat as directional only._
