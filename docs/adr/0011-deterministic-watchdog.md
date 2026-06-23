---
status: Accepted
date: 2026-05-08
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0011: Deterministic Watchdog

## Context and Problem Statement

During OS-layer remediation the Watchdog agent runs concurrently with Remediation (via `asyncio.TaskGroup`) and observes cluster health on a fixed poll interval. When health degrades, the Watchdog signals `WatchdogResult.degraded=True` and the Orchestrator issues `git-mcp revert_commit` followed by `flux-mcp reconcile_kustomization` for K8s faults (for OS faults, a non-confirmed staged generation reverts when the armed `rollback-gate.timer` fires). This path is safety-critical: a false negative (missed degradation) leaves a broken node live; a false positive triggers an unnecessary rollback that aborts a valid repair.

Two properties of LLM-backed health assessment make it unsuitable for this path:

1. **Hallucination surface**: An LLM interpreting `get_pods` output could reason itself into "the pods look mostly fine" despite a CrashLoopBackOff, particularly when tool output is incomplete. A deterministic predicate has no such failure mode.
2. **Token cost and latency**: The Watchdog polls every few seconds throughout the entire remediation window. Calling an LLM per poll tick adds hundreds of milliseconds per call and accumulates significant token cost over the confirm window with no accuracy gain over a structured status check.

The original implementation classified health *relative to a baseline snapshot captured after the fault was already live*: it only flagged states strictly worse than that broken baseline. This model proved unsound. In a k8s-2g run, Flux applied the correct fix, but the rollout's transient pod dip read as degradation while the recovered state, being merely "not worse than broken", never registered as recovery, so the run aborted a valid repair. The baseline-relative model also misread a no-op remediation (cluster equally broken) as success, counted a `Running 0/1` crashlooping pod as healthy because pod classification matched the phase string and ignored the `READY x/y` fraction, and never confirmed that the fix's revision was the one Flux applied. Production deployments have no clean pre-fault baseline at all.

The Watchdog must instead answer one absolute question: *did the target workload actually recover?* That is decidable from Kubernetes-native rollout criteria plus the Flux applied revision, with no baseline required.

## Decision Drivers

- Zero hallucination surface in the rollback decision
- No token cost in the Watchdog poll loop
- No added latency: deterministic snapshot diff is sub-millisecond vs. 100-500 ms per LLM call
- Clean separation of concerns: Watchdog observes and classifies; Orchestrator decides and acts

## Considered Options

- Deterministic Watchdog (pure Python absolute-health predicate over structured status, no LLM)
- LLM-backed Watchdog (Pydantic AI agent calling `get_pods` + LLM health reasoning)
- External alerting (Prometheus AlertManager driving rollback via webhook)

## Decision Outcome

Chosen option: "Deterministic Watchdog", because it eliminates hallucination surface from the rollback path entirely, operates at poll-loop frequency with no token overhead, and the Orchestrator retains sole rollback authority. Health is now classified by an **absolute workload-health predicate** rather than a baseline-relative delta.

### Consequences

- Good: The rollback trigger path contains no LLM call; recovery classification is a deterministic predicate over a structured `HealthSnapshot`. For a Deployment or StatefulSet target it mirrors the Kubernetes rollout-complete criteria (`observedGeneration` has caught up to `generation`, every replica is updated, ready, and available, the `Available` condition is not `False`, and `Progressing` is not `False`) with a `ProgressDeadlineExceeded` fast-fail. It additionally gates on the Flux Kustomization being Ready and, when an expected revision is known, on the Flux applied revision matching the fix's SHA. A non-workload target falls back to namespace liveness.
- Good: For an OS sysctl recovery the Watchdog confirms the live kernel parameter against an expected value derived from declarative git truth, not from an alert label. The Orchestrator reads the expected value from the declared NixOS config keyed by the drifted parameter the Diagnosis agent reported (`discovered_sysctl_key`), then wires the key and expected value to the Watchdog, which polls `get_sysctl` and treats the node as recovered once the live value matches. Absent an agent-reported key, a node-level alert is verified directly against the node's reported conditions: the Watchdog polls `describe_node` and treats the node as recovered once the relevant condition holds (`DiskPressure` is `False` for a disk-pressure alert, `Ready` is `True` for a node-not-ready alert). When the alert instead names a systemd unit, the Watchdog confirms that unit is active.
- Good: The predicate is debounced over `WATCHDOG_HEALTHY_STREAK_K` consecutive healthy polls and bounded by `WATCHDOG_WINDOW_S`, so a transient mid-rollout dip no longer aborts a valid repair and a brief healthy flap no longer declares premature success.
- Good: Because the predicate is absolute, it works for normal production deployments with no clean pre-fault baseline, and a no-op remediation that leaves the cluster broken is correctly classified as not recovered.
- Good: Watchdog poll loop incurs zero token cost regardless of how many ticks occur during the remediation window.
- Good: The Watchdog only returns `WatchdogResult`; the Orchestrator calls `revert_commit`. No agent can bypass this boundary.
- Bad: The predicate cannot reason about partial degradation (e.g., a pod that is Ready but serving 5xx responses); application-layer health is outside the Watchdog's scope.
- Bad: Health classification logic must be maintained in Python; adding a new signal (e.g., HPA scale-down event) requires a code change, not a prompt update.
- Bad: Recovery scenarios that the baseline-relative model aborted (k8s-2g class) now classify as successful, which shifts recorded outcome and MTTR metrics; an eval re-run is required to refresh the baseline figures.

**Validation Status:** Verified. Watchdog implementation in `agents/watchdog/` contains no LLM calls; health assessment is a pure-Python predicate over `HealthSnapshot`. ADR-0005 confirms Watchdog runs concurrently with Remediation via `asyncio.TaskGroup` for the parallel path. Updated 2026-05-15 for the GitOps pivot: the rollback verb is `revert_commit` followed by `reconcile_kustomization` (GitOps path). Updated 2026-06-05: classification changed from a baseline-relative degradation diff to an absolute workload-health predicate, motivated by the k8s-2g incident above; the deterministic-Watchdog rationale is unchanged. The Watchdog still observes, the Orchestrator still decides.

### Confirmation

The decision holds as long as:
- `agents/watchdog/src/watchdog/agent.py` contains no `model=` parameter or LLM client instantiation
- `is_workload_healthy` evaluated over a `HealthSnapshot` is the sole basis for `WatchdogResult.degraded`
- The Orchestrator (not the Watchdog) issues `revert_commit` in response to `WatchdogResult.degraded=True`

### Pros and Cons of the Options

#### Deterministic Watchdog

- Good: The absolute-health predicate is a pure function; given identical cluster state it always produces the same `WatchdogResult`
- Good: Poll loop can run at 1-5 s intervals with no cost; LLM-backed polling at the same cadence would accumulate hundreds of LLM calls per eval scenario
- Bad: Cannot infer health signals outside the MCP tool surface (e.g., application-level error rates in Prometheus)

#### LLM-backed Watchdog

- Good: Could reason about ambiguous partial-degradation states that a threshold comparison would miss
- Bad: An LLM interpreting `get_pods` output can produce a "mostly healthy" conclusion from a degraded cluster because it is trained to hedge uncertainty. In the rollback path, this hallucination surface directly delays a safety-critical intervention: a node running a bad NixOS configuration would remain active past the dead-man's switch window, potentially losing quorum.

#### External alerting (Prometheus AlertManager)

- Good: Purpose-built for production alerting; handles sustained degradation, flap suppression, and routing
- Bad: AlertManager requires a Prometheus stack inside the cluster. During OS-layer repairs the cluster itself may be partially degraded; relying on in-cluster alerting to detect cluster degradation creates a circular dependency where the monitor and the monitored share the same failure domain. A pod-count diff executed from outside the cluster (via `kubectl-mcp`) does not share this failure domain.

## More Information

- Multi-agent architecture and `asyncio.TaskGroup` concurrency: `docs/adr/0005-multi-agent-architecture.md`
- Dead-man's switch and rollback gate: `docs/adr/0004-nixos-dead-mans-switch.md`
- Watchdog implementation: `agents/watchdog/src/watchdog/agent.py`
