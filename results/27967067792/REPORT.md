# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 39 | 0.82 | 136.35 | 83.60 | 0.84 (32/38) | 0.08 | 0.03 | 1.00 | 208974.71/2275.50 | 15.47 | 6.42 |

## Per-Scenario Summary

33/39 runs passed, 5 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 220 ± 4 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 219 ± 2 | 3/3 | 10 | 17 |
| k8s-3g | 3/3 | OK OK OK | 220 ± 4 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 213 ± 10 | 3/3 | 10 | 15 |
| k8s-5g | 3/3 | OK OK OK | 225 ± 2 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 6 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK KO OK | 70 ± 6 | 2/3 | 6 | 24 |
| os-1g | 3/3 | OK OK OK | 128 ± 11 | 3/3 | 10 | 27 |
| os-drift-sysctl | 3/3 | OK OK OK | 56 ± 11 | 3/3 | 4 | 16 |
| os-stale-generation | 2/3 | OK KO OK | 74 ± 5 | 2/3 | 4 | 24 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC KO TO | 21 | 1/2 | 4 | 7 |
| disk-pressure | 3/3 | ESC ESC ESC | 50 ± 25 | 3/3 | 1 | 15 |
| live-quota-injected | 3/3 | ESC ESC ESC | 21 ± 7 | 3/3 | 1 | 5 |

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
| disk-pressure | os | 3/3 | 1.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
