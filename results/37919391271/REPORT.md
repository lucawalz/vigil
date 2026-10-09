# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

Target: runner.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gpt-oss:120b | 13 | 0.23 | 21.91 | 7.68 | 0.75 (9/12) | 0.15 | 0.00 | — | 81175.77/4673.08 | 10.38 | 8.15 |

## Per-Scenario Summary

3/13 runs passed, 9 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
3/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 0/1 | KO | — | 1/1 | 8 | 8 |
| k8s-2g | 0/1 | KO | — | 1/1 | 10 | 11 |
| k8s-3g | 0/1 | KO | — | 1/1 | 10 | 13 |
| k8s-4g | 0/1 | ?? | — | — | — | — |
| k8s-5g | 0/1 | ?? | — | 1/1 | 20 | 25 |
| k8s-rollback-1 | 0/1 | ?? | — | 1/1 | 19 | 25 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK | 23 | 1/1 | 4 | 7 |
| os-1g | 0/1 | KO | — | 1/1 | 13 | 15 |
| os-drift-sysctl | 0/1 | ESC | — | 0/1 | 1 | 8 |
| os-stale-generation | 1/1 | OK | 29 | 1/1 | 4 | 5 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/1 | ?? | — | 0/1 | 12 | 13 |
| disk-pressure | 0/1 | KO | — | 0/1 | 4 | 5 |
| live-quota-injected | 1/1 | ESC | 14 | 1/1 | 1 | 0 |

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
| os-1g | os | 1/1 | 1.00 |
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign - std values omitted._
