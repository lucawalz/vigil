# Eval Campaign Aggregation Report

Total runs: 39 across 1 models and 13 scenarios.

## Per-Model Summary

| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| qwen3.5:cloud | 39 | 0.72 | 168.75 | 86.08 | 0.76 (29/38) | 0.00 | 0.00 | — | 109366.63/4643.05 | 10.61 | 5.63 |

## Per-Scenario Summary

28/39 runs passed, 11 agent-failed, 0 infra-error, 0 gate-uncertain, 0 awaiting-review, 0 not-run
6/13 scenarios passed all seeds

#### Kubernetes Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| k8s-1g | 2/3 | TO OK OK | 208 ± 20 | 2/2 | 7 | 8 |
| k8s-2g | 3/3 | OK OK OK | 261 ± 35 | 3/3 | 10 | 14 |
| k8s-3g | 3/3 | OK OK OK | 250 ± 45 | 3/3 | 10 | 15 |
| k8s-4g | 3/3 | OK OK OK | 197 ± 2 | 3/3 | 10 | 14 |
| k8s-5g | 3/3 | OK OK OK | 254 ± 72 | 3/3 | 10 | 15 |
| k8s-rollback-1 | 0/3 | ?? ESC ESC | — | 1/3 | 4 | 11 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### OS / NixOS Layer

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| os-1 | 1/3 | ESC ESC OK | 231 | 1/3 | 2 | 13 |
| os-1g | 2/3 | OK OK KO | 158 ± 17 | 2/3 | 8 | 12 |
| os-drift-sysctl | 3/3 | OK OK OK | 65 ± 12 | 3/3 | 4 | 8 |
| os-stale-generation | 2/3 | OK ESC OK | 140 ± 38 | 2/3 | 3 | 12 |

legend: OK success  RB rollback  ESC escalated  TO abort/timeout  SE setup_error  KO healthy but fix not credited

#### Infrastructure / Misc

| scenario | pass | s1 s2 s3 | MTTR mean±std | diag | iters | tools |
|---|---:|---|---:|---:|---:|---:|
| deceptive-2 | 1/3 | ESC ESC ESC | 23 | 1/3 | 1 | 2 |
| disk-pressure | 2/3 | ESC ESC ESC | 113 ± 13 | 2/3 | 1 | 7 |
| live-quota-injected | 3/3 | ESC ESC ESC | 50 ± 18 | 3/3 | 1 | 4 |

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
| os-1 | os | 1/3 | 0.33 |
| os-1g | os | 2/3 | 0.67 |
| os-drift-sysctl | os | 3/3 | 1.00 |
| os-stale-generation | os | 2/3 | 0.67 |
| disk-pressure | os | 2/3 | 0.67 |

---

_Note: std values computed from 3 seeds per cell; treat as directional only._
