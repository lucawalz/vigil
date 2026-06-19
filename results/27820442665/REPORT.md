# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.79 | 427.65 | 269.43 | 0.82 (31/38) | 0.00 | 0.03 | 1.00 | 223286.62/4027.92 | 17.95 | 6.36 |

## Per-Scenario Summary

31/39 runs passed, 7 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
10/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 360 ± 36 | 3/3 | 10 | 15 |
| k8s-2g | 3/3 | OK OK OK | 475 ± 81 | 3/3 | 10 | 21 |
| k8s-3g | 3/3 | OK OK OK | 417 ± 90 | 3/3 | 10 | 20 |
| k8s-4g | 3/3 | OK OK OK | 383 ± 37 | 3/3 | 10 | 18 |
| k8s-5g | 3/3 | OK OK OK | 354 ± 44 | 3/3 | 10 | 17 |
| k8s-rollback-1 | 1/3 | ESC ESC RB | 1762 | 1/3 | 7 | 25 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 347 ± 25 | 3/3 | 5 | 22 |
| os-1g | 3/3 | OK OK OK | 593 ± 68 | 3/3 | 10 | 27 |
| os-drift-sysctl | 3/3 | OK OK OK | 271 ± 98 | 3/3 | 4 | 16 |
| os-stale-generation | 3/3 | OK OK OK | 371 ± 74 | 3/3 | 4 | 20 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 12 |
| disk-pressure | 0/3 | ESC ESC ?? | — | 0/2 | 1 | 12 |
| live-quota-injected | 3/3 | ESC ESC ESC | 262 ± 63 | 3/3 | 1 | 13 |

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
| os-1 | os | 3/3 | 1.00 |
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 0/2 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
