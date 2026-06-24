# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.74 | 197.90 | 83.42 | 0.74 (29/39) | 0.13 | 0.05 | 1.00 | 151415.46/5922.51 | 13.62 | 6.82 |

## Per-Scenario Summary

31/39 runs passed, 8 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
7/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 261 ± 34 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 226 ± 49 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 260 ± 34 | 3/3 | 10 | 16 |
| k8s-4g | 3/3 | OK OK OK | 264 ± 39 | 3/3 | 10 | 14 |
| k8s-5g | 2/3 | OK ESC OK | 249 ± 45 | 2/3 | 7 | 14 |
| k8s-rollback-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 8 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | OK KO KO | 93 | 1/3 | 13 | 35 |
| os-1g | 3/3 | OK OK OK | 228 ± 46 | 3/3 | 10 | 17 |
| os-drift-sysctl | 3/3 | OK OK OK | 133 ± 55 | 3/3 | 4 | 12 |
| os-stale-generation | 2/3 | OK OK ESC | 273 ± 42 | 2/3 | 3 | 17 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | KO KO ESC | 86 | 1/3 | 8 | 9 |
| disk-pressure | 2/3 | ESC KO ESC | 95 ± 4 | 2/3 | 2 | 6 |
| live-quota-injected | 3/3 | ESC ESC ESC | 71 ± 45 | 3/3 | 1 | 5 |

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
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
