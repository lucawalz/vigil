# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.72 | 174.82 | 109.88 | 0.74 (28/38) | 0.00 | 0.03 | 1.00 | 121719.38/4781.92 | 11.08 | 5.62 |

## Per-Scenario Summary

28/39 runs passed, 10 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 223 ± 3 | 3/3 | 10 | 11 |
| k8s-2g | 3/3 | OK OK OK | 217 ± 8 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 235 ± 41 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 235 ± 49 | 3/3 | 10 | 14 |
| k8s-5g | 3/3 | OK OK OK | 228 ± 3 | 3/3 | 10 | 12 |
| k8s-rollback-1 | 1/3 | ESC ESC RB | 546 | 1/3 | 4 | 8 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 15 |
| os-1g | 2/3 | OK ?? OK | 95 ± 1 | 2/2 | 10 | 14 |
| os-drift-sysctl | 3/3 | OK OK OK | 54 ± 5 | 3/3 | 4 | 7 |
| os-stale-generation | 3/3 | OK OK OK | 139 ± 52 | 3/3 | 4 | 20 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 6 |
| disk-pressure | 1/3 | ESC ESC ESC | 60 | 1/3 | 1 | 8 |
| live-quota-injected | 3/3 | ESC ESC ESC | 36 ± 17 | 3/3 | 1 | 5 |

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
| os-1 | os | 0/3 | 0.00 |
| os-1g | os | 2/2 | 1.00 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
