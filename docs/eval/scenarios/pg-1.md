# Scenario: pg-1 — postgresql-crashloop

**Layer:** k8s
**Root-cause layer:** k8s
**Correct action class:** apply_patch

## What This Scenario Tests

This scenario models a bad image tag on the PostgreSQL StatefulSet that causes the primary pod to enter `ImagePullBackOff`. The root-cause component is `StatefulSet/postgresql primary pod ImagePullBackOff (bad image tag)`. The PostgreSQL image is set to `bitnami/postgresql:bogus-tag-v0`, which does not exist in the registry.

## Why This Scenario Was Chosen

A StatefulSet variant of the k8s image-pull pattern (complementing k8s-1). StatefulSets have different rollout semantics from Deployments — `rollout_undo` on a StatefulSet has different behaviour. This scenario verifies that `apply_patch` (restoring the correct image) is the correct action class for StatefulSet faults, and that the agent handles prod-sim workloads (PostgreSQL) rather than only the test `vigil-app` deployment.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/pg-1/inject.sh <seed>
```

Sets the `postgresql` container image in `StatefulSet/postgresql` to `bitnami/postgresql:bogus-tag-v0` via `kubectl set image`, triggering `ImagePullBackOff` on the primary pod.

**Reset:**
```bash
./eval/scenarios/pg-1/reset.sh <seed>
```

Sets the `postgresql` container image back to `docker.io/bitnami/postgresql:16`, waits for StatefulSet rollout completion, and resumes the `flux-system` kustomization.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis -> flux_suspend -> apply_patch (restore image) -> watchdog_confirm -> flux_resume"`:

1. **Diagnosis layer:** kubectl-mcp reports `ImagePullBackOff` on `StatefulSet/postgresql` primary pod; image `bitnami/postgresql:bogus-tag-v0` is identified as the fault
2. **Escalation decision:** `requires_os_level=False` — fault is entirely within the Kubernetes layer; no OS escalation
3. **Remediation:** `apply_patch` to restore the image to `docker.io/bitnami/postgresql:16` after `flux_suspend`; Flux is resumed after the StatefulSet pod returns to Running
4. **Watchdog:** `StatefulSet/postgresql` primary pod returns to Running; database connectivity restored

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- StatefulSet rollout semantics differ from Deployment rollout; `kubectl rollout undo statefulset/postgresql` restores the previous revision, but the correct action class is `apply_patch` (set the known-good image explicitly)
- The correct image tag is `docker.io/bitnami/postgresql:16` (with the full registry prefix); omitting `docker.io/` may work but is not the canonical form in the manifest
- PostgreSQL data persistence is via PVC; the scenario does not touch the PVC and no data loss occurs
