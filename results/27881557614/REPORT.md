# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.72 | 306.73 | 339.22 | 0.81 (30/37) | 0.00 | 0.05 | 1.00 | 215095.97/4477.03 | 17.92 | 6.68 |

## Per-Scenario Summary

29/39 runs passed, 9 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
6/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 300 ± 34 | 3/3 | 10 | 15 |
| k8s-2g | 2/3 | KO OK OK | 270 ± 71 | 3/3 | 11 | 24 |
| k8s-3g | 3/3 | OK OK OK | 282 ± 63 | 3/3 | 10 | 19 |
| k8s-4g | 3/3 | OK OK OK | 282 ± 64 | 3/3 | 10 | 18 |
| k8s-5g | 2/3 | OK OK ?? | 310 ± 33 | 3/3 | 11 | 17 |
| k8s-rollback-1 | 1/3 | TO RB ESC | 1950 | 1/2 | 11 | 44 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | TO OK ESC | 44 | 1/2 | 2 | 15 |
| os-1g | 3/3 | OK OK OK | 226 ± 99 | 3/3 | 10 | 20 |
| os-drift-sysctl | 3/3 | OK OK OK | 157 ± 90 | 3/3 | 4 | 13 |
| os-stale-generation | 3/3 | OK OK OK | 299 ± 247 | 3/3 | 4 | 17 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 13 |
| disk-pressure | 2/3 | ESC ESC ESC | 224 ± 106 | 2/3 | 1 | 14 |
| live-quota-injected | 2/3 | ESC ESC ESC | 175 ± 49 | 2/3 | 1 | 12 |

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
| os-1 | os | 1/2 | 0.50 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
