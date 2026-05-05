# Scenario: redis-1 — redis-oom-eviction

**Layer:** k8s
**Root-cause layer:** k8s
**Correct action class:** apply_patch

## What This Scenario Tests

This scenario models an excessively low memory limit on the `StatefulSet/redis-master` that causes the Redis container to be OOMKilled. The root-cause component is `StatefulSet/redis-master OOMKilled (memory limit 10Mi)`. The memory limit is set to 10Mi — far below the Redis process baseline — causing every pod start to terminate with exit code 137.

## Why This Scenario Was Chosen

A StatefulSet variant of the k8s memory-limit pattern (complementing k8s-3). Verifies that the agent handles OOMKill remediation on prod-sim workloads (Redis StatefulSet) with the correct `apply_patch` action. Tests the agent's ability to restore resource limits on a stateful workload where restart behaviour differs from a Deployment.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/redis-1/inject.sh <seed>
```

Sets `resources.limits.memory` to `10Mi` on the `redis` container in `StatefulSet/redis-master` via `kubectl set resources`, causing OOMKill on every pod start.

**Reset:**
```bash
./eval/scenarios/redis-1/reset.sh <seed>
```

Restores `resources.limits.memory` to `256Mi` and `resources.requests.memory` to `128Mi`, waits for StatefulSet rollout completion, and resumes the `flux-system` kustomization.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis -> flux_suspend -> apply_patch (restore memory limit) -> watchdog_confirm -> flux_resume"`:

1. **Diagnosis layer:** kubectl-mcp reports OOMKilled exit code (137) on `StatefulSet/redis-master` pods; resource limits show `10Mi` memory cap
2. **Escalation decision:** `requires_os_level=False` — fault is entirely within the Kubernetes resource spec; no OS escalation
3. **Remediation:** `apply_patch` to restore `resources.limits.memory` to an adequate value (e.g., `256Mi`) after `flux_suspend`; Flux is resumed after the StatefulSet pod returns to Running
4. **Watchdog:** `StatefulSet/redis-master` pod returns to Running; OOMKill events cease

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- `10Mi` is syntactically valid but semantically insufficient for Redis; the agent must detect the OOMKill exit code to identify this as a memory limit fault rather than an application crash
- The correct memory limit is `256Mi` and the correct request is `128Mi` per the reset script; setting limits too low (e.g., 64Mi) may appear to work but will OOMKill under load
- Redis is a StatefulSet; rollout behaviour under resource limit changes may require a pod delete rather than a rolling update. The agent should verify pod status after patching
