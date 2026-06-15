# Eval Campaign Aggregation Report

Total runs: 26 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 26 | 0.81 | 489.23 | 224.59 | 0.81 (21/26) | 0.00 | 0.04 | 1.00 | 231617.50/4162.96 | 18.73 | 6.46 |

## Per-Scenario Summary

21/26 runs passed, 5 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 13 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/2 | OK OK | 406 ± 79 | 2/2 | 10 | 18 |
| k8s-2g | 2/2 | OK OK | 557 ± 34 | 2/2 | 10 | 20 |
| k8s-3g | 2/2 | OK OK | 428 ± 33 | 2/2 | 10 | 17 |
| k8s-4g | 2/2 | OK OK | 580 ± 167 | 2/2 | 10 | 20 |
| k8s-5g | 2/2 | OK OK | 466 ± 84 | 2/2 | 10 | 20 |
| k8s-rollback-1 | 2/2 | OK RB | 1034 ± 307 | 2/2 | 10 | 26 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/2 | OK OK | 364 ± 87 | 2/2 | 4 | 20 |
| os-1g | 2/2 | OK OK | 487 ± 108 | 2/2 | 10 | 26 |
| os-drift-sysctl | 2/2 | OK OK | 240 ± 28 | 2/2 | 4 | 12 |
| os-stale-generation | 1/2 | ESC OK | 412 | 1/2 | 2 | 20 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/2 | ESC ESC | 273 | 1/2 | 1 | 12 |
| disk-pressure | 0/2 | ESC ESC | — | 0/2 | 1 | 17 |
| live-quota-injected | 1/2 | ESC ESC | 463 | 1/2 | 1 | 17 |

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

_Note: std values computed from 2 seeds per cell; treat as directional only._
