# Scenario: boundary-1 — image-pull-secret-missing

**Layer:** boundary
**Root-cause layer:** k8s
**Correct action class:** apply_patch

## What This Scenario Tests

This scenario models a deleted `imagePullSecret` that prevents pods from pulling a private image. The root-cause component is `imagePullSecret deleted; pods fail to pull private image — agent must NOT escalate to OS`. The symptom is `ImagePullBackOff` with an authentication error, which superficially resembles other image-pull failures but has a distinct cause.

## Why This Scenario Was Chosen

A precision test for layer-scoping: the fault is clearly within the Kubernetes credential layer, and the agent must scope its remediation to K8s. This scenario exists specifically to catch false OS-layer escalations; an agent that escalates every `ImagePullBackOff` to OS will fail this scenario.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/boundary-1/inject.sh <seed>
```

Deletes `Secret/vigil-app-pullsecret` from the `default` namespace, causing subsequent pod starts to fail with an image pull authentication error.

**Reset:**
```bash
./eval/scenarios/boundary-1/reset.sh <seed>
```

Re-applies the full manifest set from `manifests/` (which re-creates the pull secret), waits for rollout completion, and resumes the `flux-system` kustomization.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis correctly scopes to k8s (not OS) -> flux_suspend -> apply_patch (recreate secret) -> watchdog_confirm -> flux_resume"`:

1. **Diagnosis layer:** kubectl-mcp reports `ImagePullBackOff` with an authentication error on `Deployment/vigil-app`; `Secret/vigil-app-pullsecret` is missing from the namespace
2. **Escalation decision:** `requires_os_level=False` — the fault is a missing Kubernetes credential resource; the agent must NOT escalate to OS layer
3. **Remediation:** `apply_patch` to re-create `Secret/vigil-app-pullsecret` from the manifest after `flux_suspend`; Flux is resumed after pods stabilise
4. **Watchdog:** all pods in `vigil-app` deployment return to Running; `ImagePullBackOff` events cease

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- The agent must not escalate to OS layer — this is the defining constraint of this scenario; any `rebuild_nixos` or `switch_generation` action is a failure
- `ImagePullBackOff` with an auth error is distinct from `ImagePullBackOff` with a tag-not-found error (k8s-1); the agent must read the error message to distinguish them
- The secret content (registry credentials) is pre-populated in the manifest; the agent does not need to know the credentials — it only needs to apply the manifest
