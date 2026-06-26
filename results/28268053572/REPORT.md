# Eval Campaign Aggregation Report

Total runs: 6 across 1 models and 6 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| deepseek-v3.2:cloud | 6 | 0.83 | 194.53 | 52.81 | 1.00 (6/6) | 0.00 | 0.00 | — | 170693.50/4543.50 | 18.83 | 9.83 |

## Per-Scenario Summary

5/6 runs passed, 1 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 33 not-run
5/6 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 223 | 1/1 | 11 | 18 |
| k8s-2g | 1/1 | OK | 221 | 1/1 | 11 | 23 |
| k8s-3g | 1/1 | OK | 216 | 1/1 | 11 | 17 |
| k8s-4g | 0/1 | ?? | — | 1/1 | 14 | 21 |
| k8s-5g | 1/1 | OK | 212 | 1/1 | 11 | 18 |
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
| live-quota-injected | 1/1 | ESC | 100 | 1/1 | 1 | 16 |

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

---

_Single-seed campaign - std values omitted._
