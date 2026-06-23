# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 13 | 0.85 | 299.49 | 213.54 | 0.92 (11/12) | 0.00 | 0.08 | 1.00 | 125753/5141.23 | 12 | 6.08 |

## Per-Scenario Summary

11/13 runs passed, 1 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
11/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 204 | 1/1 | 10 | 12 |
| k8s-2g | 1/1 | OK | 339 | 1/1 | 10 | 13 |
| k8s-3g | 1/1 | OK | 323 | 1/1 | 10 | 15 |
| k8s-4g | 1/1 | OK | 278 | 1/1 | 10 | 13 |
| k8s-5g | 1/1 | OK | 339 | 1/1 | 10 | 14 |
| k8s-rollback-1 | 1/1 | RB | 886 | 1/1 | 11 | 17 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK | 234 | 1/1 | 4 | 21 |
| os-1g | 0/1 | KO | — | 0/1 | 4 | 9 |
| os-drift-sysctl | 1/1 | OK | 198 | 1/1 | 4 | 11 |
| os-stale-generation | 1/1 | OK | 297 | 1/1 | 4 | 24 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/1 | ESC | 139 | 1/1 | 1 | 4 |
| disk-pressure | 0/1 | SE | — | — | — | — |
| live-quota-injected | 1/1 | ESC | 58 | 1/1 | 1 | 3 |

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
| os-1g | os | 0/1 | 0.00 |
| os-drift-sysctl | os | 1/1 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | — | N/A |

---

_Single-seed campaign - std values omitted._
