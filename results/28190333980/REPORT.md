# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.79 | 201.98 | 137.67 | 0.86 (31/36) | 0.10 | 0.05 | 1.00 | 210827.03/4843.49 | 19.62 | 9.11 |

## Per-Scenario Summary

33/39 runs passed, 4 agent-failed, 2 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 346 ± 218 | 3/3 | 15 | 22 |
| k8s-2g | 3/3 | OK OK OK | 323 ± 181 | 3/3 | 13 | 24 |
| k8s-3g | 3/3 | OK OK OK | 219 ± 4 | 3/3 | 11 | 17 |
| k8s-4g | 3/3 | OK OK OK | 283 ± 59 | 3/3 | 11 | 17 |
| k8s-5g | 3/3 | OK OK OK | 242 ± 37 | 3/3 | 11 | 20 |
| k8s-rollback-1 | 1/3 | SE OK ?? | 197 | 1/2 | 10 | 32 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 59 ± 9 | 3/3 | 4 | 14 |
| os-1g | 3/3 | OK OK OK | 117 ± 19 | 3/3 | 10 | 19 |
| os-drift-sysctl | 3/3 | OK OK OK | 80 ± 33 | 3/3 | 4 | 15 |
| os-stale-generation | 2/3 | OK OK KO | 85 ± 8 | 2/3 | 6 | 17 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | TO KO KO | — | 0/2 | 17 | 38 |
| disk-pressure | 1/3 | KO ESC TO | 98 | 1/2 | 2 | 7 |
| live-quota-injected | 3/3 | ESC ESC ESC | 263 ± 208 | 3/3 | 3 | 10 |

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
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 1/2 | 0.50 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
