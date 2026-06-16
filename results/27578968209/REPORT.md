# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.90 | 197.95 | 124.36 | 0.90 (35/39) | 0.00 | 0.05 | 1.00 | 123745.49/5065.46 | 11.62 | 6.13 |

## Per-Scenario Summary

35/39 runs passed, 4 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 259 ± 69 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 259 ± 38 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 258 ± 40 | 3/3 | 10 | 16 |
| k8s-4g | 3/3 | OK OK OK | 239 ± 27 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 213 ± 19 | 3/3 | 10 | 14 |
| k8s-rollback-1 | 2/3 | ESC RB RB | 572 ± 43 | 2/3 | 8 | 12 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 171 ± 38 | 3/3 | 4 | 18 |
| os-1g | 2/3 | OK OK KO | 198 ± 6 | 2/3 | 8 | 15 |
| os-drift-sysctl | 3/3 | OK OK OK | 67 ± 10 | 3/3 | 4 | 7 |
| os-stale-generation | 2/3 | OK OK ESC | 157 ± 84 | 2/3 | 3 | 15 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 2/3 | ESC ESC ESC | 58 ± 34 | 2/3 | 1 | 4 |
| disk-pressure | 3/3 | ESC ESC ESC | 138 ± 39 | 3/3 | 1 | 7 |
| live-quota-injected | 3/3 | ESC ESC ESC | 50 ± 13 | 3/3 | 1 | 4 |

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
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 3/3 | 1.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
