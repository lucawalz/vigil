# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.85 | 357.36 | 193.18 | 0.89 (34/38) | 0.00 | 0.05 | 1.00 | 213390.97/4523.55 | 17.76 | 6.66 |

## Per-Scenario Summary

34/39 runs passed, 5 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 3/3 | OK OK OK | 320 ± 94 | 3/3 | 10 | 15 |
| k8s-2g | 2/3 | OK OK KO | 508 ± 102 | 3/3 | 12 | 24 |
| k8s-3g | 3/3 | OK OK OK | 381 ± 188 | 3/3 | 11 | 20 |
| k8s-4g | 3/3 | OK OK OK | 380 ± 150 | 3/3 | 10 | 20 |
| k8s-5g | 2/3 | OK TO OK | 467 ± 6 | 2/2 | 7 | 24 |
| k8s-rollback-1 | 2/3 | OK RB ESC | 763 ± 177 | 2/3 | 9 | 24 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 3/3 | OK OK OK | 300 ± 214 | 3/3 | 4 | 20 |
| os-1g | 3/3 | OK OK OK | 473 ± 252 | 3/3 | 11 | 22 |
| os-drift-sysctl | 3/3 | OK OK OK | 213 ± 145 | 3/3 | 4 | 16 |
| os-stale-generation | 3/3 | OK OK OK | 223 ± 130 | 3/3 | 4 | 21 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 2/3 | ESC ESC ESC | 334 ± 29 | 2/3 | 1 | 11 |
| disk-pressure | 1/3 | ESC ESC ESC | 194 | 1/3 | 1 | 10 |
| live-quota-injected | 3/3 | ESC ESC ESC | 195 ± 150 | 3/3 | 1 | 11 |

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
| disk-pressure | os | 1/3 | 0.33 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
