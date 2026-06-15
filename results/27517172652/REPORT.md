# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.79 | 203.50 | 132.20 | 0.82 (31/38) | 0.00 | 0.05 | 1.00 | 119329.71/5480.68 | 11.71 | 6.32 |

## Per-Scenario Summary

31/39 runs passed, 8 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 208 ± 14 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 238 ± 23 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 216 ± 4 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 220 ± 1 | 3/3 | 10 | 13 |
| k8s-5g | 2/3 | OK OK TO | 254 ± 42 | 2/2 | 8 | 14 |
| k8s-rollback-1 | 2/3 | RB RB ESC | 627 ± 67 | 2/3 | 8 | 13 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 217 ± 40 | 3/3 | 4 | 17 |
| os-1g | 3/3 | OK OK OK | 160 ± 37 | 3/3 | 10 | 16 |
| os-drift-sysctl | 3/3 | OK OK OK | 61 ± 12 | 3/3 | 4 | 6 |
| os-stale-generation | 3/3 | OK OK OK | 121 ± 21 | 3/3 | 4 | 14 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 5 |
| disk-pressure | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 7 |
| live-quota-injected | 3/3 | ESC ESC ESC | 75 ± 41 | 3/3 | 1 | 5 |

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
| disk-pressure | os | 0/3 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
