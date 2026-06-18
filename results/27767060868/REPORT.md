# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 39 | 0.79 | 131.69 | 83.84 | 0.82 (31/38) | 0.00 | 0.00 | — | 181732.66/2199.26 | 14.13 | 5.74 |

## Per-Scenario Summary

31/39 runs passed, 8 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 192 ± 47 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 221 ± 2 | 3/3 | 10 | 18 |
| k8s-3g | 3/3 | OK OK OK | 220 ± 1 | 3/3 | 10 | 16 |
| k8s-4g | 3/3 | OK OK OK | 222 ± 2 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 204 ± 33 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 5 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK OK ESC | 71 ± 3 | 2/3 | 3 | 23 |
| os-1g | 3/3 | OK OK OK | 112 ± 14 | 3/3 | 10 | 25 |
| os-drift-sysctl | 3/3 | OK OK OK | 39 ± 3 | 3/3 | 4 | 6 |
| os-stale-generation | 1/3 | ESC TO OK | 71 | 1/2 | 2 | 19 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC ESC ESC | 58 | 1/3 | 1 | 16 |
| disk-pressure | 3/3 | ESC ESC ESC | 39 ± 14 | 3/3 | 1 | 13 |
| live-quota-injected | 3/3 | ESC ESC ESC | 22 ± 5 | 3/3 | 1 | 5 |

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
| os-stale-generation | os | 1/2 | 0.50 |
| disk-pressure | os | 3/3 | 1.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
