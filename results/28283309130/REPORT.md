# Eval Campaign Aggregation Report

Total runs: 4 across 1 models and 4 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 4 | 0.50 | 312.41 | 124.84 | 1.00 (3/3) | 0.00 | 0.00 | — | 192673.67/7013 | 20.33 | 11.67 |

## Per-Scenario Summary

2/4 runs passed, 1 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 35 not-run
2/4 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 401 | 1/1 | 11 | 19 |
| k8s-2g | 1/1 | OK | 224 | 1/1 | 11 | 23 |
| k8s-3g | 0/1 | ?? | — | 1/1 | 13 | 19 |
| k8s-4g | 0/1 | TO | — | — | 1 | 0 |
| k8s-5g | no data | — | — | — | — | — |
| k8s-rollback-1 | no data | — | — | — | — | — |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | no data | — | — | — | — | — |
| os-1g | no data | — | — | — | — | — |
| os-drift-sysctl | no data | — | — | — | — | — |
| os-stale-generation | no data | — | — | — | — | — |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | no data | — | — | — | — | — |
| disk-pressure | no data | — | — | — | — | — |
| live-quota-injected | no data | — | — | — | — | — |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| k8s-1g | k8s | — | N/A |
| k8s-2g | k8s | — | N/A |
| k8s-3g | k8s | — | N/A |
| k8s-4g | k8s | — | N/A |

---

_Single-seed campaign - std values omitted._
