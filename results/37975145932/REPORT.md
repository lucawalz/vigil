# Eval Campaign Aggregation Report

Total runs: 13 across 1 models and 13 scenarios.

Target: runner.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| gpt-oss:120b | 13 | 0.46 | 140.74 | 135.16 | 0.60 (6/10) | 0.15 | 0.08 | 0.00 | 49897.17/2899.58 | 6.33 | 5.33 |

## Per-Scenario Summary

6/13 runs passed, 4 agent-failed, 3 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
6/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 1/1 | OK | 252 | 1/1 | 10 | 10 |
| k8s-2g | 0/1 | ?? | — | — | — | — |
| k8s-3g | 1/1 | OK | 284 | 1/1 | 10 | 11 |
| k8s-4g | 0/1 | ?? | — | — | — | — |
| k8s-5g | 1/1 | OK | 254 | 1/1 | 10 | 12 |
| k8s-rollback-1 | 0/1 | TO | — | — | 10 | 14 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/1 | OK | 21 | 1/1 | 4 | 6 |
| os-1g | 0/1 | KO | — | 0/1 | 4 | 5 |
| os-drift-sysctl | 0/1 | ESC | — | 0/1 | 1 | 7 |
| os-stale-generation | 1/1 | OK | 18 | 1/1 | 4 | 4 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/1 | ?? | — | 0/1 | 17 | 17 |
| disk-pressure | 0/1 | KO | — | 0/1 | 3 | 4 |
| live-quota-injected | 1/1 | ESC | 15 | 1/1 | 1 | 0 |

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
| os-drift-sysctl | os | 0/1 | 0.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 0/1 | 0.00 |

---

_Single-seed campaign - std values omitted._
