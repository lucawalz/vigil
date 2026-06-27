# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.82 | 192.96 | 164.97 | 0.84 (32/38) | 0.10 | 0.13 | 1.00 | 156611.89/6139.11 | 13.42 | 7.16 |

## Per-Scenario Summary

35/39 runs passed, 4 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 194 ± 43 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 220 ± 5 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 222 ± 4 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 219 ± 3 | 3/3 | 10 | 13 |
| k8s-5g | 2/3 | OK TO OK | 227 ± 2 | 2/2 | 7 | 11 |
| k8s-rollback-1 | 2/3 | RB ESC RB | 588 ± 9 | 2/3 | 8 | 12 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK OK KO | 89 ± 5 | 2/3 | 6 | 19 |
| os-1g | 2/3 | OK OK KO | 163 ± 15 | 2/3 | 8 | 17 |
| os-drift-sysctl | 3/3 | OK OK OK | 99 ± 36 | 3/3 | 4 | 14 |
| os-stale-generation | 3/3 | OK OK OK | 318 ± 369 | 3/3 | 5 | 25 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | KO KO KO | — | 0/3 | 11 | 12 |
| disk-pressure | 3/3 | ESC ESC ESC | 44 ± 24 | 3/3 | 1 | 5 |
| live-quota-injected | 3/3 | ESC ESC ESC | 30 ± 12 | 3/3 | 1 | 3 |

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
| disk-pressure | os | 3/3 | 1.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
