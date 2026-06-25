# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 39 | 0.82 | 141.69 | 80.62 | 0.82 (32/39) | 0.10 | 0.08 | 1.00 | 225084.44/2441.69 | 16.23 | 6.77 |

## Per-Scenario Summary

35/39 runs passed, 4 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
10/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 220 ± 3 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 223 ± 3 | 3/3 | 10 | 15 |
| k8s-3g | 3/3 | OK OK OK | 218 ± 5 | 3/3 | 10 | 18 |
| k8s-4g | 3/3 | OK OK OK | 218 ± 3 | 3/3 | 10 | 15 |
| k8s-5g | 3/3 | OK OK OK | 224 ± 2 | 3/3 | 10 | 14 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 8 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 81 ± 3 | 3/3 | 4 | 23 |
| os-1g | 3/3 | OK OK OK | 142 ± 18 | 3/3 | 10 | 27 |
| os-drift-sysctl | 3/3 | OK OK OK | 67 ± 14 | 3/3 | 4 | 20 |
| os-stale-generation | 3/3 | OK OK OK | 75 ± 5 | 3/3 | 4 | 23 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 12 | 21 |
| disk-pressure | 2/3 | ESC KO ESC | 37 ± 16 | 2/3 | 2 | 11 |
| live-quota-injected | 3/3 | ESC ESC ESC | 20 ± 2 | 3/3 | 1 | 4 |

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
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
