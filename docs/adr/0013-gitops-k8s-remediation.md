---
status: Accepted
date: 2026-05-16
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0013: K8s-layer remediation via GitOps

## Context and Problem Statement

K8s-layer remediation originally followed a suspend-before-mutate pattern noted incidentally in ADR-0005: Flux would be suspended, the repair patch applied imperatively with `kubectl`, and Flux resumed. This approach has two structural problems.

First, there is no audit trail for the patch: if an eval campaign run fails to reproduce, the imperative mutation is not recorded in version control and cannot be replayed deterministically.

Second, the suspend window introduces drift between cluster state and Git declarations. While Flux is suspended, the cluster is running configuration that does not correspond to any commit. If the agent crashes during this window, Flux resumes to reconcile a stale ref, leaving the cluster in an undefined state that is neither the pre-patch baseline nor the intended repair.

The NixOS rollback path already uses a version-control-backed mechanism: `nixos-mcp switch_generation` reverts to a known-good NixOS generation. The K8s path lacked a symmetric mechanism.

## Decision Drivers

- Eval campaign reproducibility requires that every K8s mutation is recorded in Git; imperative patches produce no audit trail
- Structural symmetry with the NixOS rollback path: both layers should revert to a known-good state in version control, neither should use imperative restart
- Flux's 1-minute GitRepository poll interval is too slow for interactive eval; agent-initiated reconciliation eliminates the timing dependency
- Suspend-during-mutation window creates drift between cluster state and Git declarations; GitOps eliminates this drift window entirely

## Considered Options

- K8s-layer remediation via GitOps (Git commit + CI validation + agent-initiated `reconcile_kustomization`)
- Direct `kubectl patch` (imperative, no commit, no CI gate)
- Suspend-before-mutate (Flux suspended, patch applied, Flux resumed)

## Decision Outcome

Chosen option: "K8s-layer remediation via GitOps", because every K8s mutation is recorded as a Git commit validated by CI and applied to the cluster via agent-initiated `flux-mcp.reconcile_kustomization`, eliminating the audit-trail gap and the suspend-window drift in a single mechanism.

The agent issues `git-mcp.commit_and_push` to create the repair commit, waits for CI to pass, then calls `flux-mcp.reconcile_kustomization` to apply the commit immediately. Flux's 1-minute GitRepository poll is the fallback if the explicit reconcile call is not issued; it is not the primary delivery mechanism.

K8s rollback is now structurally symmetric to NixOS rollback — both revert to a known-good state declared in version control (Git for K8s, NixOS generations for OS), neither uses imperative restart.

### Consequences

- Good: Every K8s mutation is a Git commit; the full repair history is auditable and can be replayed deterministically across eval campaign runs
- Good: No suspend window: the cluster always tracks the HEAD of the GitOps repository; there is no period during which the cluster state diverges from any commit
- Good: Agent-initiated `reconcile_kustomization` eliminates the 1-minute Flux poll delay for interactive eval; the rollback path (`revert_commit` + `reconcile_kustomization`) is symmetric to the repair path
- Good: The Watchdog observes cluster health after reconciliation; the Orchestrator retains sole rollback authority via `revert_commit`
- Bad: CI validation adds latency to the repair path; a failing CI pipeline blocks the repair until fixed or the run is aborted as gate_failed
- Bad: The GitOps path requires a live Git remote and CI runner; a network partition isolating the agent host from GitHub blocks both the commit push and the CI gate

**Validation Status:** Pending — gitops validation campaign verification

### Confirmation

The decision holds as long as:
- The Remediation agent uses `git-mcp.commit_and_push` for all K8s mutations (no direct `kubectl patch` calls on the K8s repair path)
- `flux-mcp.reconcile_kustomization` is called by the agent after the CI gate passes
- `WatchdogResult.degraded=True` triggers `git-mcp.revert_commit` followed by `flux-mcp.reconcile_kustomization` (not a `kubectl` rollback)
- `RunRecord.agent_branch` and `RunRecord.agent_commits` record the GitOps trail for every successful K8s repair

### Pros and Cons of the Options

#### K8s-layer remediation via GitOps

- Good: Git commit history is the complete record of every K8s repair; no out-of-band mutations exist that are invisible to version control
- Good: Rollback is `git-mcp.revert_commit` followed by `flux-mcp.reconcile_kustomization` — structurally identical to the repair path, deterministic and auditable
- Bad: Requires network access to GitHub for every repair; an isolated eval environment without external connectivity cannot use this path

#### Direct `kubectl patch`

- Good: Immediate effect; no CI gate latency and no Flux reconcile delay
- Bad: An imperative `kubectl patch` leaves no record in Git, making it impossible to reconstruct which exact mutation was applied during a given eval run. When a campaign run fails to reproduce, there is no commit to inspect, diff, or replay — blocking the forensic analysis that reproducibility of eval campaign runs requires.

#### Suspend-before-mutate

- Good: Allows `kubectl` edits without Flux immediately reconciling them away; no Git remote dependency
- Bad: Suspending Flux while applying a patch creates a window during which the cluster state does not correspond to any Git commit. If the agent crashes after patching but before resuming Flux, the cluster runs configuration that diverges from all declared states indefinitely — neither the pre-patch baseline nor the intended repair — making incident recovery ambiguous.

## More Information

- Multi-agent architecture and the suspend-before-mutate consequence this decision reframes: `docs/adr/0005-multi-agent-architecture.md`
- Deterministic Watchdog and the GitOps rollback verb (`revert_commit` + `reconcile_kustomization`): `docs/adr/0011-deterministic-watchdog.md`
