# Eval Campaign Aggregation Report

Total runs: 26 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| claude-sonnet-4-6 | 26 | 0.73 | 151.76 | 84.65 | 0.76 (19/25) | 0.12 | 0.08 | 1.00 | 223267.52/2450.44 | 15.60 | 6.72 |

## Per-Scenario Summary

21/26 runs passed, 4 agent-failed, 1 infra-error, 0 gate-uncertain, 0 awaiting-review, 13 not-run
8/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/2 | OK OK | 179 ± 61 | 2/2 | 10 | 12 |
| k8s-2g | 2/2 | OK OK | 220 ± 2 | 2/2 | 10 | 16 |
| k8s-3g | 2/2 | OK OK | 223 ± 1 | 2/2 | 10 | 16 |
| k8s-4g | 2/2 | OK OK | 224 ± 3 | 2/2 | 10 | 14 |
| k8s-5g | 2/2 | OK OK | 221 ± 0 | 2/2 | 10 | 14 |
| k8s-rollback-1 | 0/2 | ESC ESC | — | 0/2 | 1 | 12 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/2 | OK ESC | 74 | 1/2 | 2 | 18 |
| os-1g | 2/2 | OK OK | 190 ± 85 | 2/2 | 10 | 28 |
| os-drift-sysctl | 2/2 | OK OK | 69 ± 9 | 2/2 | 4 | 22 |
| os-stale-generation | 1/2 | OK TO | 85 | 1/1 | 4 | 23 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 0/2 | KO KO | — | 0/2 | 11 | 12 |
| disk-pressure | 1/2 | ESC KO | 31 | 1/2 | 2 | 16 |
| live-quota-injected | 2/2 | ESC ESC | 19 ± 1 | 2/2 | 1 | 4 |

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
| os-1 | os | 1/2 | 0.50 |
| os-1g | os | 2/2 | 1.00 |
| os-drift-sysctl | os | 2/2 | 1.00 |
| os-stale-generation | os | 1/1 | 1.00 |
| disk-pressure | os | 1/2 | 0.50 |

---

_Note: std values computed from 2 seeds per cell; treat as directional only._
