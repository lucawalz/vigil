# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.95 | 247.38 | 179.56 | 0.95 (37/39) | 0.03 | 0.10 | 1.00 | 136831.46/5717.54 | 12.08 | 6.72 |

## Per-Scenario Summary

38/39 runs passed, 1 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
11/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 212 ± 7 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 260 ± 34 | 3/3 | 10 | 13 |
| k8s-3g | 3/3 | OK OK OK | 325 ± 70 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 222 ± 1 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 233 ± 44 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 3/3 | RB RB RB | 735 ± 196 | 3/3 | 11 | 16 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 176 ± 39 | 3/3 | 4 | 18 |
| os-1g | 2/3 | KO OK OK | 371 ± 140 | 2/3 | 8 | 15 |
| os-drift-sysctl | 3/3 | OK OK OK | 201 ± 40 | 3/3 | 4 | 12 |
| os-stale-generation | 3/3 | OK OK OK | 200 ± 64 | 3/3 | 4 | 15 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 2/3 | ESC KO ESC | 40 ± 30 | 2/3 | 4 | 6 |
| disk-pressure | 3/3 | ESC ESC ESC | 162 ± 80 | 3/3 | 1 | 6 |
| live-quota-injected | 3/3 | ESC ESC ESC | 52 ± 20 | 3/3 | 1 | 2 |

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
| os-1g | os | 2/3 | 0.67 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 3/3 | 1.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
