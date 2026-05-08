# Eval Scenarios

18 deterministic fault injection scenarios used in the evaluation campaign. Each scenario has an inject script, a reset script, and ground-truth labels in `eval/scenarios/<id>/scenario.yaml`.

## Scenarios

| Scenario | Group | Layer | Root-cause Layer | Correct Action |
|----------|-------|-------|-----------------|----------------|
| [cross-1](cross-1.md) | cross | cross | os | rebuild_nixos |
| [cross-2](cross-2.md) | cross | cross | os | rebuild_nixos |
| [cross-3](cross-3.md) | cross | cross | os | rebuild_nixos |
| [k8s-1](k8s-1.md) | k8s | k8s | k8s | rollout_undo |
| [k8s-2](k8s-2.md) | k8s | k8s | k8s | apply_patch |
| [k8s-3](k8s-3.md) | k8s | k8s | k8s | apply_patch |
| [k8s-4](k8s-4.md) | k8s | k8s | k8s | apply_patch |
| [k8s-5](k8s-5.md) | k8s | k8s | k8s | apply_patch |
| [os-1](os-1.md) | os | os | os | switch_generation |
| [os-2](os-2.md) | os | os | os | rebuild_nixos |
| [os-3](os-3.md) | os | os | os | rebuild_nixos |
| [boundary-1](boundary-1.md) | misc | boundary | k8s | apply_patch |
| [boundary-2](boundary-2.md) | misc | boundary | k8s | apply_patch |
| [boundary-3](boundary-3.md) | misc | boundary | k8s | apply_patch |
| [boundary-4](boundary-4.md) | misc | boundary | k8s | apply_patch |
| [pg-1](pg-1.md) | misc | k8s | k8s | apply_patch |
| [redis-1](redis-1.md) | misc | k8s | k8s | apply_patch |
| [ingress-1](ingress-1.md) | misc | k8s | k8s | apply_patch |
