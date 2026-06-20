# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 39 | 0.90 | 126.95 | 86.80 | 0.90 (35/39) | 0.00 | 0.00 | — | 170353.05/2079.31 | 13.51 | 5.77 |

## Per-Scenario Summary

35/39 runs passed, 4 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
11/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 193 ± 46 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 241 ± 32 | 3/3 | 10 | 17 |
| k8s-3g | 3/3 | OK OK OK | 218 ± 4 | 3/3 | 10 | 14 |
| k8s-4g | 3/3 | OK OK OK | 220 ± 1 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 223 ± 4 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 5 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK ESC OK | 75 ± 7 | 2/3 | 3 | 22 |
| os-1g | 3/3 | OK OK OK | 115 ± 30 | 3/3 | 10 | 24 |
| os-drift-sysctl | 3/3 | OK OK OK | 47 ± 12 | 3/3 | 4 | 8 |
| os-stale-generation | 3/3 | OK OK OK | 81 ± 17 | 3/3 | 4 | 24 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 3/3 | ESC ESC ESC | 27 ± 2 | 3/3 | 1 | 7 |
| disk-pressure | 3/3 | ESC ESC ESC | 45 ± 18 | 3/3 | 1 | 14 |
| live-quota-injected | 3/3 | ESC ESC ESC | 21 ± 1 | 3/3 | 1 | 4 |

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
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 3/3 | 1.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
