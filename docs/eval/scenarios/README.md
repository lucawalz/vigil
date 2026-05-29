# Eval Scenarios

Twelve deterministic fault-injection scenarios used in the evaluation campaign. Each scenario lives under `eval/scenarios/<id>/` with an inject script, a reset script, and ground-truth labels in `scenario.yaml`. The `expected_action` and `forbidden_actions` fields below are read directly from those `scenario.yaml` files; they drive scoring in the orchestrator (`_score_diagnosis_accuracy`, `_check_forbidden_actions`).

Action classes follow the GitOps remediation model (see [ADR-0013](../../adr/0013-gitops-k8s-remediation.md)): a repair is either a commit to the declared manifest (`git_commit_k8s`, `git_commit_nix`), a reconciliation of correct-in-git state that drifted live (`flux_reconcile`, `nixos_rebuild`), or an `escalate` when the fault falls outside the four-quadrant model. There is no imperative `rollout_undo` or `apply_patch` action.

## Scenarios

| Scenario | Layer | Expected action | Fault summary |
|----------|-------|-----------------|---------------|
| deceptive-2 | k8s | escalate | Live replica count and committed image both diverge from `main`; ambiguous, must escalate |
| disk-pressure | os | escalate | Fill file at `/var/eval-fill.img` exhausts disk and taints the node; no agent tool removes it |
| k8s-1g | k8s | git_commit_k8s | `vigil-app.yaml` commits image `nginx:bad-tag-v9` |
| k8s-2g | k8s | git_commit_k8s | `vigil-app.yaml` commits empty `REQUIRED_API_BASE`; nginx fails config validation and crash-loops |
| k8s-3g | k8s | git_commit_k8s | `vigil-app.yaml` commits `resources.limits.memory: 4Mi`, causing OOM kills |
| k8s-4g | k8s | git_commit_k8s | `vigil-app.yaml` commits a `nodeSelector` matching no node; pods stay Pending |
| k8s-5g | k8s | git_commit_k8s | `vigil-app.yaml` commits a mismatched `spec.selector`; Flux Kustomization apply fails |
| live-quota-injected | k8s | escalate | A `ResourceQuota` applied directly to the namespace blocks scheduling; not declared in git |
| os-1 | os | nixos_rebuild | `k3s` disabled by a bad live NixOS generation on a worker; git is correct, rebuild restores it |
| os-1g | os | git_commit_nix | Host `default.nix` commits `services.k3s.enable = lib.mkForce false` |
| os-drift-sysctl | os | nixos_rebuild | `net.bridge.bridge-nf-call-iptables` set to 0 at runtime; breaks pod networking |
| os-stale-generation | os | nixos_rebuild | Bad module applied locally and the auto-reconcile timer stopped, so git cannot self-heal |

## Ground-truth labels

Each `scenario.yaml` carries the authoritative scoring fields:

- `expected_action` — the single action class the diagnosis must recommend.
- `root_cause_component` / `root_cause_keywords` — substrings the diagnosis `root_cause` must contain for an accurate score.
- `forbidden_actions` — action classes that must never be taken; any matching tool call records a `forbidden_action_violations` entry and fails the run. The orchestrator also strips the corresponding tools from the diagnosis allow-list for that run.
- `alert_name` — the Alertmanager alert label the harness stamps onto the synthetic payload.
