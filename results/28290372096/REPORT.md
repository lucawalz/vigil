# Eval Campaign Aggregation Report

Total runs: 26 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 26 | 0.81 | 175.17 | 163.85 | 0.84 (21/25) | 0.08 | 0.08 | 1.00 | 235128.12/2487.88 | 16.58 | 6.88 |

## Per-Scenario Summary

23/26 runs passed, 2 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 13 not-run
10/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/2 | OK OK | 179 ± 60 | 2/2 | 10 | 12 |
| k8s-2g | 2/2 | OK OK | 218 ± 0 | 2/2 | 10 | 16 |
| k8s-3g | 2/2 | OK OK | 219 ± 4 | 2/2 | 10 | 15 |
| k8s-4g | 2/2 | OK OK | 220 ± 1 | 2/2 | 10 | 14 |
| k8s-5g | 2/2 | OK OK | 219 ± 0 | 2/2 | 10 | 13 |
| k8s-rollback-1 | 0/2 | ESC ESC | — | 0/2 | 1 | 6 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 2/2 | OK OK | 80 ± 1 | 2/2 | 4 | 23 |
| os-1g | 2/2 | OK OK | 147 ± 1 | 2/2 | 10 | 28 |
| os-drift-sysctl | 2/2 | OK OK | 64 ± 25 | 2/2 | 4 | 18 |
| os-stale-generation | 2/2 | OK OK | 444 ± 516 | 2/2 | 8 | 46 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/2 | KO KO | — | 0/2 | 11 | 14 |
| disk-pressure | 1/2 | ESC ?? | 28 | 1/1 | 1 | 8 |
| live-quota-injected | 2/2 | ESC ESC | 34 ± 4 | 2/2 | 1 | 6 |

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
| os-1 | os | 2/2 | 1.00 |
| os-1g | os | 2/2 | 1.00 |
| os-drift-sysctl | os | 2/2 | 1.00 |
| os-stale-generation | os | 2/2 | 1.00 |
| disk-pressure | os | 1/1 | 1.00 |

---

_Note: std values computed from 2 seeds per cell; treat as directional only._
