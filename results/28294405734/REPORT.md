# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 39 | 0.77 | 138.31 | 79.93 | 0.77 (30/39) | 0.10 | 0.08 | 1.00 | 220311.97/2481.33 | 16.03 | 6.72 |

## Per-Scenario Summary

33/39 runs passed, 6 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 165 ± 51 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 225 ± 3 | 3/3 | 10 | 17 |
| k8s-3g | 3/3 | OK OK OK | 220 ± 2 | 3/3 | 10 | 16 |
| k8s-4g | 3/3 | OK OK OK | 218 ± 1 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 221 ± 2 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 8 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | OK ESC ESC | 81 | 1/3 | 3 | 21 |
| os-1g | 3/3 | OK OK OK | 125 ± 14 | 3/3 | 10 | 25 |
| os-drift-sysctl | 3/3 | OK OK OK | 64 ± 8 | 3/3 | 4 | 19 |
| os-stale-generation | 3/3 | OK OK OK | 76 ± 12 | 3/3 | 4 | 22 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 12 | 22 |
| disk-pressure | 2/3 | ESC KO ESC | 34 ± 5 | 2/3 | 2 | 15 |
| live-quota-injected | 3/3 | ESC ESC ESC | 21 ± 0 | 3/3 | 1 | 4 |

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
| os-1g | os | 3/3 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
