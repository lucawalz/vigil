# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.74 | 413.96 | 316.08 | 0.76 (29/38) | 0.00 | 0.03 | 1.00 | 226083.79/4164.82 | 18.61 | 6.08 |

## Per-Scenario Summary

29/39 runs passed, 9 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 413 ± 30 | 3/3 | 10 | 16 |
| k8s-2g | 3/3 | OK OK OK | 443 ± 60 | 3/3 | 10 | 19 |
| k8s-3g | 3/3 | OK OK OK | 387 ± 92 | 3/3 | 10 | 23 |
| k8s-4g | 3/3 | OK OK OK | 413 ± 46 | 3/3 | 10 | 19 |
| k8s-5g | 3/3 | OK OK OK | 397 ± 73 | 3/3 | 10 | 17 |
| k8s-rollback-1 | 1/3 | RB ESC ESC | 1969 | 1/3 | 7 | 29 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | ESC OK ESC | 580 | 1/3 | 2 | 20 |
| os-1g | 2/3 | OK OK TO | 308 ± 47 | 2/2 | 10 | 20 |
| os-drift-sysctl | 3/3 | OK OK OK | 220 ± 65 | 3/3 | 4 | 15 |
| os-stale-generation | 3/3 | OK OK OK | 345 ± 103 | 3/3 | 4 | 23 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 11 |
| disk-pressure | 1/3 | ESC ESC ESC | 242 | 1/3 | 1 | 17 |
| live-quota-injected | 3/3 | ESC ESC ESC | 247 ± 76 | 3/3 | 1 | 14 |

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
| os-1g | os | 2/2 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
