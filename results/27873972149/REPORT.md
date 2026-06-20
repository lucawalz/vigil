# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.26 | 173.77 | 89.34 | 0.67 (10/15) | 0.00 | 0.00 | — | 176465.67/3860.67 | 15.87 | 5.27 |

## Per-Scenario Summary

10/39 runs passed, 29 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/3 | OK TO TO | 227 | 1/1 | 4 | 6 |
| k8s-2g | 1/3 | OK TO TO | 221 | 1/1 | 4 | 6 |
| k8s-3g | 1/3 | OK TO TO | 218 | 1/1 | 4 | 6 |
| k8s-4g | 1/3 | OK TO TO | 220 | 1/1 | 5 | 5 |
| k8s-5g | 2/3 | OK TO OK | 279 ± 6 | 2/2 | 8 | 13 |
| k8s-rollback-1 | 0/3 | ESC TO ESC | — | 0/2 | 1 | 9 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | TO TO OK | 65 | 1/1 | 2 | 6 |
| os-1g | 0/3 | TO TO TO | — | — | 1 | 2 |
| os-drift-sysctl | 0/3 | TO TO TO | — | — | 1 | 0 |
| os-stale-generation | 0/3 | TO TO ESC | — | 0/1 | 1 | 5 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC TO ESC | 64 | 1/2 | 1 | 8 |
| disk-pressure | 0/3 | TO TO ESC | — | 0/1 | 1 | 5 |
| live-quota-injected | 2/3 | ESC TO ESC | 83 ± 2 | 2/2 | 1 | 10 |

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
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | — | N/A |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | 0/1 | 0.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
