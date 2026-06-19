# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.51 | 339.96 | 210.42 | 0.80 (20/25) | 0.00 | 0.03 | 1.00 | 220806.20/3846.20 | 17.64 | 5.84 |

## Per-Scenario Summary

20/39 runs passed, 17 agent-failed, 2 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | TO OK OK | 355 ± 106 | 2/2 | 7 | 11 |
| k8s-2g | 1/3 | TO TO OK | 599 | 1/1 | 6 | 11 |
| k8s-3g | 2/3 | TO OK OK | 374 ± 41 | 2/2 | 7 | 13 |
| k8s-4g | 2/3 | TO OK OK | 358 ± 67 | 2/2 | 7 | 13 |
| k8s-5g | 2/3 | TO OK OK | 346 ± 83 | 2/2 | 7 | 12 |
| k8s-rollback-1 | 1/3 | TO TO RB | 1110 | 1/1 | 6 | 12 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/3 | TO ESC ESC | — | 0/2 | 1 | 10 |
| os-1g | 2/3 | TO OK OK | 237 ± 29 | 2/2 | 7 | 15 |
| os-drift-sysctl | 2/3 | TO OK OK | 199 ± 59 | 2/2 | 3 | 9 |
| os-stale-generation | 2/3 | TO OK OK | 247 ± 12 | 2/2 | 3 | 13 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | TO ESC ESC | 278 | 1/2 | 1 | 10 |
| disk-pressure | 1/3 | ESC ESC ESC | 162 | 1/3 | 1 | 18 |
| live-quota-injected | 2/3 | TO ESC ESC | 210 ± 26 | 2/2 | 1 | 9 |

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
| os-1 | os | 0/2 | 0.00 |
| os-1g | os | 2/2 | 1.00 |
| os-drift-sysctl | os | 2/2 | 1.00 |
| os-stale-generation | os | 2/2 | 1.00 |
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
