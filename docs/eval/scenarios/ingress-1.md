# Scenario: ingress-1 — ingress-backend-missing

**Layer:** k8s
**Root-cause layer:** k8s
**Correct action class:** apply_patch

## What This Scenario Tests

This scenario models a deleted backend Service that causes the ingress controller to return HTTP 502 for all requests routed through the affected Ingress rule. The root-cause component is `Service/vigil-app-svc deleted (ingress returns 502)`. The Ingress resource itself remains intact; only the backend Service is missing.

## Why This Scenario Was Chosen

Exercises Service deletion and ingress backend recovery. Tests the agent's ability to diagnose an HTTP-level failure (502 from ingress), trace it to the missing backend Service, and re-create the Service via `apply_patch` rather than modifying the Ingress or the Deployment.

## Inject / Reset Commands

**Inject:**
```bash
./eval/scenarios/ingress-1/inject.sh <seed>
```

Deletes `Service/vigil-app-svc` from the `default` namespace, causing the ingress controller to lose its backend endpoint and return 502 for affected routes.

**Reset:**
```bash
./eval/scenarios/ingress-1/reset.sh <seed>
```

Re-applies the full manifest set from `manifests/` (which re-creates the Service), verifies the Service exists, and resumes the `flux-system` kustomization.

## Expected Agent Reasoning Path

Steps from `expected_resolution_path: "diagnosis -> flux_suspend -> apply_patch (re-create service) -> watchdog_confirm -> flux_resume"`:

1. **Diagnosis layer:** kubectl-mcp observes `Service/vigil-app-svc` missing from the `default` namespace; Ingress resource exists but has no valid backend endpoint
2. **Escalation decision:** `requires_os_level=False` — fault is entirely within the Kubernetes networking layer; no OS escalation
3. **Remediation:** `apply_patch` to re-create `Service/vigil-app-svc` from the manifest after `flux_suspend`; Flux is resumed after the Service is available
4. **Watchdog:** ingress routes return HTTP 200; Service endpoint is populated in the Endpoints resource

## Success Criteria

- Agent identifies root-cause layer correctly (k8s vs os)
- Agent escalates to OS layer if and only if root_cause_layer=os
- Remediation matches correct_action_class
- Watchdog confirms recovery (no destructive_repair=true in run record)

## Known Edge Cases

- The Ingress resource and the Deployment both remain intact; the agent must identify the missing Service specifically, not attempt a Deployment restart or Ingress modification
- reset.sh verifies the Service exists after apply and exits non-zero if it is still missing, ensuring the reset completes cleanly before the next scenario
- Ingress controller endpoint propagation can take a few seconds after the Service is re-created; the watchdog must allow time for the endpoint slice to update before checking HTTP responses
