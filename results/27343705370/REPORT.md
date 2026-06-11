# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 39 | 0.00 | — | — | — | 0.00 | 0.00 | — | —/— | — | — |

## Per-Scenario Summary

0/39 runs passed, 39 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
0/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 0/3 | TO TO TO | — | — | 1 | 0 |
| k8s-2g | 0/3 | TO TO TO | — | — | 1 | 0 |
| k8s-3g | 0/3 | TO TO TO | — | — | 1 | 0 |
| k8s-4g | 0/3 | TO TO TO | — | — | 1 | 0 |
| k8s-5g | 0/3 | TO TO TO | — | — | 1 | 0 |
| k8s-rollback-1 | 0/3 | TO TO TO | — | — | 1 | 0 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/3 | TO TO TO | — | — | 1 | 0 |
| os-1g | 0/3 | TO TO TO | — | — | 1 | 0 |
| os-drift-sysctl | 0/3 | TO TO TO | — | — | 1 | 0 |
| os-stale-generation | 0/3 | TO TO TO | — | — | 1 | 0 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/3 | TO TO TO | — | — | 1 | 0 |
| disk-pressure | 0/3 | TO TO TO | — | — | 1 | 0 |
| live-quota-injected | 0/3 | TO TO TO | — | — | 1 | 0 |

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
| os-1 | os | — | N/A |
| os-1g | os | — | N/A |
| os-drift-sysctl | os | — | N/A |
| os-stale-generation | os | — | N/A |
| disk-pressure | os | — | N/A |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
