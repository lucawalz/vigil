# Eval Campaign Aggregation Report

Total runs: 5 across 1 models and 5 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 5 | 0.80 | 139.33 | 62.87 | 0.80 (4/5) | 0.00 | 0.00 | — | 137563.20/4969.60 | 10.40 | 4.20 |

## Per-Scenario Summary

4/5 runs passed, 1 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 34 not-run
4/5 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | no data | — | — | — | — | — |
| k8s-2g | no data | — | — | — | — | — |
| k8s-3g | no data | — | — | — | — | — |
| k8s-4g | no data | — | — | — | — | — |
| k8s-5g | no data | — | — | — | — | — |
| k8s-rollback-1 | no data | — | — | — | — | — |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK | 158 | 1/1 | 5 | 18 |
| os-1g | 1/1 | OK | 200 | 1/1 | 10 | 15 |
| os-drift-sysctl | 1/1 | OK | 51 | 1/1 | 4 | 6 |
| os-stale-generation | 0/1 | ESC | — | 0/1 | 1 | 8 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | no data | — | — | — | — | — |
| disk-pressure | 1/1 | ESC | 148 | 1/1 | 1 | 5 |
| live-quota-injected | no data | — | — | — | — | — |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

## Cross-Layer Escalation Accuracy

| Scenario | Layer | Correct/Total | Accuracy |
|---|---|---:|---:|
| os-1 | os | 1/1 | 1.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 0/1 | 0.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Single-seed campaign — std values omitted._
