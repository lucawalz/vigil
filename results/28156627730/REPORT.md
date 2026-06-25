# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.90 | 222.29 | 167.55 | 0.92 (36/39) | 0.03 | 0.13 | 1.00 | 145984.18/6032.18 | 12.33 | 6.74 |

## Per-Scenario Summary

37/39 runs passed, 2 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 220 ± 3 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 259 ± 40 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 318 ± 172 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 220 ± 0 | 3/3 | 10 | 13 |
| k8s-5g | 3/3 | OK OK OK | 222 ± 1 | 3/3 | 10 | 11 |
| k8s-rollback-1 | 3/3 | RB RB RB | 654 ± 64 | 3/3 | 11 | 15 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK ESC OK | 216 ± 68 | 2/3 | 3 | 15 |
| os-1g | 2/3 | OK KO OK | 262 ± 35 | 3/3 | 10 | 20 |
| os-drift-sysctl | 3/3 | OK OK OK | 119 ± 31 | 3/3 | 4 | 13 |
| os-stale-generation | 2/3 | OK ESC OK | 187 ± 113 | 2/3 | 3 | 16 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 2/3 | ESC ESC KO | 39 ± 17 | 2/3 | 4 | 7 |
| disk-pressure | 3/3 | ESC ESC ESC | 78 ± 1 | 3/3 | 1 | 7 |
| live-quota-injected | 3/3 | ESC ESC ESC | 34 ± 6 | 3/3 | 1 | 3 |

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
