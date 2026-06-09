# Eval Campaign Aggregation Report

Total runs: 31 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 31 | 0.65 | 209.05 | 94.77 | 0.67 (20/30) | 0.00 | 0.00 | — | 113587.61/4603.94 | 10.48 | 5.13 |

## Per-Scenario Summary

20/31 runs passed, 10 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 8 not-run
7/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/2 | OK OK — | 213 ± 13 | 2/2 | 10 | 12 |
| k8s-2g | 2/2 | OK OK — | 251 ± 39 | 2/2 | 10 | 13 |
| k8s-3g | 2/2 | OK OK — | 252 ± 44 | 2/2 | 10 | 14 |
| k8s-4g | 2/2 | OK OK — | 204 ± 23 | 2/2 | 10 | 13 |
| k8s-5g | 2/2 | OK OK — | 202 ± 16 | 2/2 | 10 | 16 |
| k8s-rollback-1 | 1/2 | ESC OK — | 342 | 1/2 | 6 | 10 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | OK SE ESC | 257 | 1/2 | 2 | 16 |
| os-1g | 1/3 | KO KO OK | 319 | 1/3 | 6 | 12 |
| os-drift-sysctl | 3/3 | OK OK OK | 79 ± 32 | 3/3 | 4 | 6 |
| os-stale-generation | 1/3 | ESC ESC OK | 422 | 1/3 | 2 | 15 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/2 | ESC ESC — | — | 0/2 | 1 | 4 |
| disk-pressure | 1/3 | ESC ESC ESC | 91 | 1/3 | 1 | 6 |
| live-quota-injected | 2/2 | ESC ESC — | 134 ± 58 | 2/2 | 1 | 6 |

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
| os-1 | os | 1/2 | 0.50 |
| os-1g | os | 1/3 | 0.33 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 1/3 | 0.33 |
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
