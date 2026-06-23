# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.72 | 187.01 | 128.93 | 0.72 (28/39) | 0.15 | 0.08 | 1.00 | 228037.18/4796.56 | 19.92 | 8.95 |

## Per-Scenario Summary

31/39 runs passed, 8 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 220 ± 5 | 3/3 | 11 | 16 |
| k8s-2g | 3/3 | OK OK OK | 284 ± 108 | 3/3 | 11 | 20 |
| k8s-3g | 3/3 | OK OK OK | 239 ± 36 | 3/3 | 11 | 18 |
| k8s-4g | 3/3 | OK OK OK | 232 ± 108 | 3/3 | 12 | 17 |
| k8s-5g | 3/3 | OK OK OK | 345 ± 210 | 3/3 | 14 | 26 |
| k8s-rollback-1 | 0/3 | ESC ESC ?? | — | 0/3 | 6 | 26 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | KO OK OK | 54 ± 1 | 2/3 | 4 | 15 |
| os-1g | 3/3 | OK OK OK | 111 ± 42 | 3/3 | 10 | 19 |
| os-drift-sysctl | 3/3 | OK OK OK | 62 ± 7 | 3/3 | 4 | 15 |
| os-stale-generation | 2/3 | OK KO OK | 84 ± 44 | 2/3 | 5 | 16 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 22 | 50 |
| disk-pressure | 0/3 | KO KO KO | — | 0/3 | 5 | 14 |
| live-quota-injected | 3/3 | ESC ESC ESC | 161 ± 177 | 3/3 | 2 | 7 |

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
| os-1 | os | 2/3 | 0.67 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
