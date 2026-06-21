# Eval Campaign Aggregation Report

Total runs: 1 across 1 models and 1 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 1 | 1.00 | 263.21 | — | 1.00 (1/1) | 0.00 | 0.00 | — | 97687/3764 | 12 | 10 |

## Per-Scenario Summary

1/1 runs passed, 0 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 12 not-run
1/1 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 263 | 1/1 | 10 | 12 |
| k8s-2g | no data | — | — | — | — | — |
| k8s-3g | no data | — | — | — | — | — |
| k8s-4g | no data | — | — | — | — | — |
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

---

_Single-seed campaign — std values omitted._
