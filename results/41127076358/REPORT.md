# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

Target: runner.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gpt-oss:120b | 13 | 0.69 | 192.01 | 270.65 | 0.69 (9/13) | 0.15 | 0.15 | 0.50 | 59128.23/3320.92 | 7.31 | 4.77 |

## Per-Scenario Summary

9/13 runs passed, 4 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
9/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 146 | 1/1 | 6 | 6 |
| k8s-2g | 1/1 | OK | 145 | 1/1 | 7 | 7 |
| k8s-3g | 1/1 | OK | 148 | 1/1 | 6 | 8 |
| k8s-4g | 1/1 | OK | 146 | 1/1 | 7 | 7 |
| k8s-5g | 1/1 | OK | 144 | 1/1 | 6 | 10 |
| k8s-rollback-1 | 1/1 | RB | 898 | 1/1 | 6 | 8 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 0/1 | ESC | — | 0/1 | 1 | 5 |
| os-1g | 1/1 | OK | 67 | 1/1 | 7 | 10 |
| os-drift-sysctl | 0/1 | ESC | — | 0/1 | 1 | 9 |
| os-stale-generation | 1/1 | OK | 24 | 1/1 | 3 | 9 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/1 | ?? | — | 0/1 | 7 | 8 |
| disk-pressure | 0/1 | KO | — | 0/1 | 4 | 5 |
| live-quota-injected | 1/1 | ESC | 10 | 1/1 | 1 | 3 |

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
| os-1 | os | 0/1 | 0.00 |
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign - std values omitted._
