# Eval Campaign Aggregation Report

Total runs: 34 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 34 | 0.44 | 530.28 | 431.28 | 0.75 (15/20) | 0.00 | 0.03 | 1.00 | 233605.45/4021.95 | 19.80 | 6.40 |

## Per-Scenario Summary

15/34 runs passed, 18 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 5 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | OK TO OK | 393 ± 75 | 2/2 | 7 | 10 |
| k8s-2g | 2/3 | OK TO OK | 549 ± 217 | 2/2 | 7 | 13 |
| k8s-3g | 1/3 | OK TO TO | 461 | 1/1 | 6 | 11 |
| k8s-4g | 2/3 | OK TO OK | 422 ± 59 | 2/2 | 7 | 14 |
| k8s-5g | 2/3 | OK TO OK | 551 ± 211 | 2/2 | 7 | 12 |
| k8s-rollback-1 | 1/3 | RB TO ESC | 2008 | 1/2 | 6 | 23 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/2 | TO ESC — | — | 0/1 | 1 | 10 |
| os-1g | 1/2 | TO OK — | 505 | 1/1 | 6 | 14 |
| os-drift-sysctl | 0/2 | TO ESC — | — | 0/1 | 1 | 9 |
| os-stale-generation | 1/2 | TO OK — | 335 | 1/1 | 2 | 10 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC TO ESC | 217 | 1/2 | 1 | 7 |
| disk-pressure | 0/2 | TO ESC — | — | 0/1 | 1 | 10 |
| live-quota-injected | 2/3 | ESC TO ESC | 298 ± 79 | 2/2 | 1 | 9 |

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
| os-1 | os | 0/1 | 0.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
