# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.77 | 290.58 | 365.79 | 0.84 (32/38) | 0.00 | 0.08 | 1.00 | 207439.42/4569.61 | 18.47 | 7.82 |

## Per-Scenario Summary

30/39 runs passed, 8 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | ?? OK OK | 400 ± 253 | 3/3 | 15 | 23 |
| k8s-2g | 2/3 | OK OK ?? | 224 ± 2 | 3/3 | 11 | 19 |
| k8s-3g | 3/3 | OK OK OK | 395 ± 259 | 3/3 | 14 | 28 |
| k8s-4g | 3/3 | OK OK OK | 241 ± 35 | 3/3 | 11 | 17 |
| k8s-5g | 3/3 | OK OK OK | 219 ± 64 | 3/3 | 11 | 18 |
| k8s-rollback-1 | 3/3 | RB RB RB | 1009 ± 830 | 3/3 | 13 | 32 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/3 | OK OK ESC | 67 ± 17 | 2/3 | 3 | 16 |
| os-1g | 3/3 | OK OK OK | 217 ± 219 | 3/3 | 10 | 18 |
| os-drift-sysctl | 3/3 | OK OK OK | 170 ± 194 | 3/3 | 4 | 18 |
| os-stale-generation | 3/3 | OK OK OK | 164 ± 192 | 3/3 | 4 | 18 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | ESC ESC ESC | — | 0/3 | 1 | 12 |
| disk-pressure | 0/3 | ESC ESC TO | — | 0/2 | 1 | 9 |
| live-quota-injected | 3/3 | ESC ESC ESC | 29 ± 6 | 3/3 | 1 | 9 |

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
| os-stale-generation | os | 3/3 | 1.00 |
| disk-pressure | os | 0/2 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
