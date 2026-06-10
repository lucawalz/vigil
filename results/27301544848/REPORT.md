# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.77 | 216.52 | 139.71 | 0.77 (30/39) | 0.00 | 0.05 | 1.00 | 113173.92/5163.95 | 11.26 | 6.05 |

## Per-Scenario Summary

30/39 runs passed, 9 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
7/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 217 ± 9 | 3/3 | 10 | 12 |
| k8s-2g | 3/3 | OK OK OK | 260 ± 32 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 317 ± 38 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 233 ± 22 | 3/3 | 10 | 14 |
| k8s-5g | 3/3 | OK OK OK | 212 ± 22 | 3/3 | 10 | 13 |
| k8s-rollback-1 | 2/3 | RB RB ESC | 637 ± 76 | 2/3 | 8 | 14 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK ESC OK | 159 ± 35 | 2/3 | 3 | 16 |
| os-1g | 2/3 | KO OK OK | 157 ± 37 | 2/3 | 8 | 12 |
| os-drift-sysctl | 3/3 | OK OK OK | 65 ± 12 | 3/3 | 4 | 7 |
| os-stale-generation | 2/3 | ESC OK OK | 152 ± 3 | 2/3 | 3 | 15 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 3 |
| disk-pressure | 1/3 | ESC ESC ESC | 148 | 1/3 | 1 | 6 |
| live-quota-injected | 3/3 | ESC ESC ESC | 76 ± 46 | 3/3 | 1 | 6 |

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
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
