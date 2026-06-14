# Eval Campaign Aggregation Report

Total runs: 34 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 34 | 0.79 | 169.42 | 98.78 | 0.79 (27/34) | 0.00 | 0.03 | 1.00 | 109622.76/4793.74 | 10.91 | 6.06 |

## Per-Scenario Summary

27/34 runs passed, 7 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 5 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 191 ± 46 | 3/3 | 10 | 11 |
| k8s-2g | 3/3 | OK OK OK | 222 ± 2 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 216 ± 5 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 222 ± 3 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 193 ± 72 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 1/3 | ESC RB ESC | 491 | 1/3 | 4 | 11 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/2 | OK OK — | 155 ± 62 | 2/2 | 4 | 18 |
| os-1g | 1/2 | KO OK — | 181 | 1/2 | 7 | 14 |
| os-drift-sysctl | 2/2 | OK OK — | 58 ± 2 | 2/2 | 4 | 8 |
| os-stale-generation | 1/2 | OK ESC — | 102 | 1/2 | 2 | 11 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC ESC ESC | 24 | 1/3 | 1 | 5 |
| disk-pressure | 1/2 | ESC ESC — | 78 | 1/2 | 1 | 6 |
| live-quota-injected | 3/3 | ESC ESC ESC | 47 ± 17 | 3/3 | 1 | 5 |

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
| os-1 | os | 2/2 | 1.00 |
| os-1g | os | 1/2 | 0.50 |
| os-drift-sysctl | os | 2/2 | 1.00 |
| os-stale-generation | os | 1/2 | 0.50 |
| disk-pressure | os | 1/2 | 0.50 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
