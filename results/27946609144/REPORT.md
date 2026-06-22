# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.87 | 299.58 | 202.61 | 0.87 (34/39) | 0.08 | 0.13 | 1.00 | 136570.21/5557.49 | 12.41 | 7.08 |

## Per-Scenario Summary

36/39 runs passed, 3 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 315 ± 30 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 294 ± 143 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 270 ± 72 | 3/3 | 10 | 14 |
| k8s-4g | 3/3 | OK OK OK | 315 ± 74 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 255 ± 49 | 3/3 | 10 | 12 |
| k8s-rollback-1 | 3/3 | RB RB RB | 825 ± 95 | 3/3 | 11 | 16 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | KO OK OK | 361 ± 229 | 2/3 | 4 | 16 |
| os-1g | 2/3 | OK OK KO | 262 ± 27 | 2/3 | 8 | 14 |
| os-drift-sysctl | 3/3 | OK OK OK | 205 ± 62 | 3/3 | 4 | 13 |
| os-stale-generation | 3/3 | OK OK OK | 313 ± 189 | 3/3 | 4 | 18 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | KO KO ESC | 129 | 1/3 | 8 | 9 |
| disk-pressure | 2/3 | ESC KO ESC | 99 ± 61 | 2/3 | 2 | 6 |
| live-quota-injected | 3/3 | ESC ESC ESC | 79 ± 38 | 3/3 | 1 | 3 |

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
| os-1g | os | 2/3 | 0.67 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
