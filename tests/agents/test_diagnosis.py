"""Diagnosis agent configuration and run_diagnosis wiring tests.

These tests verify structural contracts (agent construction, toolset scope,
usage limits, prompt content) without running the live LLM.
"""

from __future__ import annotations

import inspect
import os

import pytest

# Provide test env vars BEFORE importing diagnosis.agent (build_model() reads them).
os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

import diagnosis.agent as _diag_module
from diagnosis.agent import _build_user_message, diagnosis_agent, run_diagnosis
from diagnosis.models import DiagnosisDeps, DiagnosisReport
from pydantic_ai import Agent


def test_diagnosis_agent_is_agent_instance() -> None:
    assert isinstance(diagnosis_agent, Agent)


def test_diagnosis_agent_output_type_is_diagnosis_report() -> None:
    source = inspect.getsource(_diag_module)
    assert "output_type=DiagnosisReport" in source
    assert DiagnosisReport.__name__ == "DiagnosisReport"


def test_run_diagnosis_is_coroutine() -> None:
    assert inspect.iscoroutinefunction(run_diagnosis)


def test_run_diagnosis_uses_only_diagnosis_scoped_toolsets() -> None:
    source = inspect.getsource(run_diagnosis)
    assert "git_readonly" in source
    assert "ssh_mcp" not in source


def test_run_diagnosis_enforces_request_limit() -> None:
    """Request ceiling via DIAGNOSIS_REQUEST_LIMIT env var (default 25)."""
    assert _diag_module.DIAGNOSIS_REQUEST_LIMIT == int(
        os.environ.get("DIAGNOSIS_REQUEST_LIMIT", "25")
    )
    source = inspect.getsource(run_diagnosis)
    assert "request_limit=DIAGNOSIS_REQUEST_LIMIT" in source


def test_run_diagnosis_wraps_read_toolsets_with_repeat_guard() -> None:
    """Each read toolset gets the repeat cap; wiring must not silently regress."""
    source = inspect.getsource(run_diagnosis)
    assert "ToolRepeatLimitToolset(" in source
    assert "limit=DIAGNOSIS_TOOL_REPEAT_LIMIT" in source
    assert "kubectl_readonly" in source
    assert "nixos_readonly" in source
    assert "git_readonly" in source
    assert "flux_readonly" in source


def test_diagnosis_system_prompt_forbids_symptom_naming() -> None:
    """System prompt must never name a symptom as root cause."""
    source = inspect.getsource(_diag_module)
    has_symptom_clause = any(
        term in source for term in ("CrashLoopBackOff", "ImagePullBackOff", "OOMKilled")
    )
    assert has_symptom_clause, "System prompt must forbid K8s symptoms as root causes"


def test_run_diagnosis_signature_accepts_diagnosis_deps() -> None:
    sig = inspect.signature(run_diagnosis)
    params = list(sig.parameters.values())
    assert len(params) == 7
    assert params[0].name == "deps"
    ann = params[0].annotation
    assert ann is DiagnosisDeps or (isinstance(ann, str) and "DiagnosisDeps" in ann)


def test_run_diagnosis_returns_tuple_with_usage() -> None:
    """Orchestrator needs usage tuple for token aggregation."""
    source = inspect.getsource(run_diagnosis)
    assert "agent_run.usage" in source
    assert "agent_run.all_messages()" in source
    assert "agent_run.result.output" in source


def test_diagnosis_system_prompt_contains_action_selection_rule() -> None:
    source = inspect.getsource(_diag_module)
    assert "recommended_action selection" in source


def test_diagnosis_report_escalate_is_valid() -> None:
    report = DiagnosisReport(
        root_cause="non-flux-managed resource",
        root_cause_component="vigil-app",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="ManifestPathError: not a Kustomization",
        drift_classification="no_drift",
        recommended_action="escalate",
        confidence=0.9,
    )
    assert report.recommended_action == "escalate"


def _base_report_kwargs(**overrides: object) -> dict:
    return {
        "root_cause": "image pull failure",
        "root_cause_component": "vigil-app:bad-tag",
        "severity": "high",
        "affected_resources": ["default/vigil-app"],
        "evidence": "ImagePullBackOff: nginx:bad-tag-v9",
        "drift_classification": "live_only_drift",
        "recommended_action": "flux_reconcile",
        "confidence": 0.95,
        **overrides,
    }


def test_drift_classification_validator_rejects_live_drift_with_git_commit() -> None:
    import pytest

    with pytest.raises(Exception, match="live_only_drift"):
        DiagnosisReport(**_base_report_kwargs(recommended_action="git_commit_k8s"))


def test_declared_drift_with_flux_reconcile_is_rejected() -> None:
    import pytest

    with pytest.raises(Exception, match="declared_drift"):
        DiagnosisReport(
            **_base_report_kwargs(
                drift_classification="declared_drift",
                recommended_action="flux_reconcile",
            )
        )


def test_drift_classification_validator_accepts_valid_pairs() -> None:
    for dc, action in [
        ("live_only_drift", "flux_reconcile"),
        ("live_only_drift", "nixos_rebuild"),
        ("declared_drift", "git_commit_k8s"),
        ("declared_drift", "git_commit_nix"),
        ("both_drift", "escalate"),
        ("no_drift", "escalate"),
    ]:
        DiagnosisReport(
            **_base_report_kwargs(drift_classification=dc, recommended_action=action)
        )


def test_system_prompt_uses_git_commit_for_k8s_faults() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    assert "git_commit_k8s" in _SYSTEM_PROMPT
    assert "delete_resource" not in _SYSTEM_PROMPT
    assert "apply_patch" not in _SYSTEM_PROMPT
    assert "rollout_undo" not in _SYSTEM_PROMPT


def test_system_prompt_mandates_lookup_manifest_path() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    assert "lookup_manifest_path" in _SYSTEM_PROMPT


def test_system_prompt_instructs_patch_body_population() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    assert "patch_body" in _SYSTEM_PROMPT


def test_system_prompt_covers_rollout_regression_reconstruction() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    assert any(
        phrase in _SYSTEM_PROMPT
        for phrase in ("rollout history", "ReplicaSet", "previous revision")
    )


def test_lookup_manifest_path_helpers_registered_as_tools() -> None:
    source = inspect.getsource(_diag_module)
    assert "@diagnosis_agent.tool_plain" in source
    assert "def lookup_os_manifest_path" in source


def test_kubectl_allow_list_excludes_delete_resource() -> None:
    from common.constants import DIAGNOSIS_KUBECTL_READ_TOOLS

    assert "delete_resource" not in DIAGNOSIS_KUBECTL_READ_TOOLS


def test_system_prompt_has_three_axis_labels() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    assert "Scheduling" in _SYSTEM_PROMPT
    assert "Runtime" in _SYSTEM_PROMPT
    assert "Node" in _SYSTEM_PROMPT


def test_system_prompt_contains_new_kubectl_tools() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    for tool in ("get_events", "describe_node", "get_taints"):
        assert tool in _SYSTEM_PROMPT, f"expected {tool!r} in _SYSTEM_PROMPT"


def test_system_prompt_contains_helmrelease_patch_rule() -> None:
    from diagnosis.agent import _SYSTEM_PROMPT

    assert "helmrelease.yaml" in _SYSTEM_PROMPT
    assert "spec.values" in _SYSTEM_PROMPT


def test_diagnosis_deps_docstring_rationale() -> None:
    assert DiagnosisDeps.__doc__ is not None
    assert "prevent tool confusion" not in DiagnosisDeps.__doc__
    assert "nixos-mcp" in DiagnosisDeps.__doc__


def test_diagnosis_report_patch_body_optional() -> None:
    r = DiagnosisReport(
        root_cause="drift",
        root_cause_component="vigil-app",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="event",
        drift_classification="declared_drift",
        recommended_action="git_commit_k8s",
        confidence=0.9,
        resource_kind="Deployment",
        resource_name="vigil-app",
        resource_namespace="default",
    )
    assert r.patch_body is None


def test_diagnosis_report_lacks_live_observed_field() -> None:
    assert "live_observed" not in DiagnosisReport.model_fields


def test_diagnosis_report_lacks_declared_observed_field() -> None:
    assert "declared_observed" not in DiagnosisReport.model_fields


def test_diagnosis_report_drift_action_consistent_validator_intact() -> None:
    report_valid = DiagnosisReport(
        root_cause="image pull failure",
        root_cause_component="vigil-app",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="ImagePullBackOff",
        drift_classification="live_only_drift",
        recommended_action="flux_reconcile",
        confidence=0.9,
    )
    assert report_valid.recommended_action == "flux_reconcile"

    with pytest.raises(Exception):
        DiagnosisReport(
            root_cause="image pull failure",
            root_cause_component="vigil-app",
            severity="high",
            affected_resources=["default/vigil-app"],
            evidence="ImagePullBackOff",
            drift_classification="live_only_drift",
            recommended_action="git_commit_k8s",
            confidence=0.9,
        )


def test_run_diagnosis_signature_requires_context() -> None:
    from diagnosis.context import DiagnosisContext

    sig = inspect.signature(run_diagnosis)
    params = sig.parameters
    assert "context" in params
    assert params["context"].default is inspect.Parameter.empty, (
        "context must be required (no default)"
    )
    ann = params["context"].annotation
    assert ann is DiagnosisContext or (
        isinstance(ann, str) and "DiagnosisContext" in ann
    )


def test_diagnosis_toolsets_use_allow_list_filter() -> None:
    from diagnosis.agent import is_diagnosis_tool_allowed

    module_source = inspect.getsource(_diag_module)
    assert "is_diagnosis_tool_allowed" in module_source
    assert "READ_TOOLS" in module_source
    assert callable(is_diagnosis_tool_allowed)


def test_flux_allow_list_excludes_reconcile_kustomization() -> None:
    from common.constants import DIAGNOSIS_FLUX_READ_TOOLS
    from diagnosis.agent import is_diagnosis_tool_allowed

    source = inspect.getsource(run_diagnosis)
    assert "flux_readonly" in source
    assert "reconcile_kustomization" not in DIAGNOSIS_FLUX_READ_TOOLS
    assert not is_diagnosis_tool_allowed(
        "reconcile_kustomization", DIAGNOSIS_FLUX_READ_TOOLS, frozenset()
    )


def test_diagnosis_context_is_frozen() -> None:
    import dataclasses

    from diagnosis.context import DiagnosisContext

    ctx = DiagnosisContext(
        source_branch="main",
        manifest_path=None,
        live_yaml="",
        declared_yaml="",
        diff="",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.source_branch = "other"  # type: ignore[misc]


def test_diagnosis_context_required_fields() -> None:
    import dataclasses

    from diagnosis.context import DiagnosisContext

    fields = {f.name: f for f in dataclasses.fields(DiagnosisContext)}
    assert set(fields.keys()) == {
        "source_branch",
        "manifest_path",
        "live_yaml",
        "declared_yaml",
        "diff",
        "live_pod_status",
        "live_admission_objects",
    }
    assert fields["source_branch"].type in (str, "str")
    assert fields["manifest_path"].type in ("str | None", "Optional[str]")
    assert fields["live_yaml"].type in (str, "str")
    assert fields["declared_yaml"].type in (str, "str")
    assert fields["diff"].type in (str, "str")
    assert fields["live_pod_status"].type in (str, "str")


def test_compute_diff_unified_format() -> None:
    from diagnosis.context import _compute_diff

    live = "image: nginx:bad\n"
    declared = "image: nginx:stable\n"
    result = _compute_diff(live, declared)
    assert "--- live" in result
    assert "+++ declared" in result
    assert "-image: nginx:bad" in result
    assert "+image: nginx:stable" in result


def test_build_diagnosis_context_k8s_happy_path() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodImagePullBackOff",
                    "namespace": "default",
                    "deployment": "vigil-app",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "KubePodImagePullBackOff"},
        commonLabels={"namespace": "default"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="KubePodImagePullBackOff"}',
    )

    kust_yaml = (
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\n"
        "kind: Kustomization\n"
        "metadata:\n"
        "  name: cluster-apps\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  path: infra/overlays/hetzner/kubernetes/clusters/hetzner/apps\n"
        "  sourceRef:\n"
        "    kind: GitRepository\n"
        "    name: flux-system\n"
    )
    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )
    live_resource_yaml = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: vigil-app\n"
        "  namespace: default\n"
        "  annotations:\n"
        "    kustomize.toolkit.fluxcd.io/name: cluster-apps\n"
        "    kustomize.toolkit.fluxcd.io/namespace: flux-system\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "      - image: nginx:bad-tag\n"
    )
    declared_yaml_content = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: vigil-app\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "      - image: nginx:stable\n"
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "Deployment":
            return {"content": live_resource_yaml}
        if kind == "Kustomization":
            return {"content": kust_yaml}
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        return {"content": ""}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(
        return_value={"content": declared_yaml_content}
    )
    mock_nixos = AsyncMock()
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))
    assert ctx.live_yaml == live_resource_yaml
    assert ctx.declared_yaml == declared_yaml_content
    assert "--- live" in ctx.diff or ctx.diff == ""
    assert ctx.source_branch == "main"
    assert ctx.manifest_path is not None


def test_build_diagnosis_context_rolled_pod_resolves_deployment() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent
    from pydantic_ai.exceptions import ModelRetry

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodCrashLooping",
                    "namespace": "default",
                    "pod": "vigil-app-6895f8ff98-5fdhb",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "KubePodCrashLooping"},
        commonLabels={"namespace": "default"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="KubePodCrashLooping"}',
    )

    kust_yaml = (
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\n"
        "kind: Kustomization\n"
        "metadata:\n"
        "  name: cluster-apps\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  path: infra/overlays/hetzner/kubernetes/clusters/hetzner/apps\n"
        "  sourceRef:\n"
        "    kind: GitRepository\n"
        "    name: flux-system\n"
    )
    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )
    deployment_yaml = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: vigil-app\n"
        "  namespace: default\n"
        "  annotations:\n"
        "    kustomize.toolkit.fluxcd.io/name: cluster-apps\n"
        "    kustomize.toolkit.fluxcd.io/namespace: flux-system\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "      - image: nginx:stable\n"
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "Pod":
            raise ModelRetry(
                "GetResourceYAML: get Pod/default/vigil-app-6895f8ff98-5fdhb: "
                'pods "vigil-app-6895f8ff98-5fdhb" not found'
            )
        if kind == "Deployment":
            assert args.get("name") == "vigil-app"
            return {"content": deployment_yaml}
        if kind == "Kustomization":
            return {"content": kust_yaml}
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        return {"content": ""}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": deployment_yaml})
    mock_nixos = AsyncMock()
    mock_flux = AsyncMock()

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))
    assert ctx.live_yaml == deployment_yaml
    assert ctx.manifest_path is not None


def test_build_diagnosis_context_pod_and_workload_gone_degrades() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent
    from pydantic_ai.exceptions import ModelRetry

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodCrashLooping",
                    "namespace": "default",
                    "pod": "vigil-app-6895f8ff98-5fdhb",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "KubePodCrashLooping"},
        commonLabels={"namespace": "default"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="KubePodCrashLooping"}',
    )
    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )
    pods_table = (
        "NAME                         READY   STATUS\n"
        "vigil-app-5fc67bd7bf-xcxdv   1/1     Running\n"
    )

    async def kubectl_side_effect(tool, args):
        if tool == "get_pods":
            return {"content": pods_table}
        if tool == "get_events":
            return {"content": ""}
        kind = args.get("kind", "")
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        if kind in ("Pod", "Deployment"):
            raise ModelRetry(f"{kind} not found")
        return {"content": ""}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": ""})
    mock_nixos = AsyncMock()
    mock_flux = AsyncMock()

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))
    assert ctx.live_yaml == ""
    assert ctx.manifest_path is None
    assert "vigil-app-5fc67bd7bf-xcxdv" in ctx.live_pod_status


def test_build_diagnosis_context_manifest_path_unresolvable() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodCrash",
                    "namespace": "default",
                    "deployment": "unmanaged-app",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "KubePodCrash"},
        commonLabels={"namespace": "default"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="KubePodCrash"}',
    )

    live_resource_yaml = (
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: unmanaged-app\n"
        "  namespace: default\n"
    )
    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "Deployment":
            return {"content": live_resource_yaml}
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        return {"content": ""}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": ""})
    mock_nixos = AsyncMock()
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    from diagnosis.context import ManifestPathUnresolvable

    with pytest.raises(ManifestPathUnresolvable):
        asyncio.run(build_diagnosis_context(deps, fault))


def test_build_diagnosis_context_read_file_failure_degrades() -> None:
    import asyncio
    from unittest.mock import AsyncMock, patch

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {"deployment": "vigil-app", "namespace": "default"},
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={},
        commonLabels={"namespace": "default"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey="{}:{}",
    )

    live_resource_yaml = "kind: Deployment\nmetadata:\n  name: vigil-app\n"
    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\nkind: GitRepository\n"
        "metadata:\n  name: flux-system\n  namespace: flux-system\n"
        "spec:\n  ref:\n    branch: main\n"
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "Deployment":
            return {"content": live_resource_yaml}
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        return {"content": ""}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)

    async def git_side_effect(tool, args):
        if tool == "clone_repo":
            return {"content": "ok"}
        raise RuntimeError("git unavailable")

    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(side_effect=git_side_effect)
    mock_nixos = AsyncMock()
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    from diagnosis.context import ManifestPathUnresolvable

    with patch(
        "diagnosis.context._resolve_manifest_path_k8s",
        return_value="apps/vigil-app.yaml",
    ):
        with pytest.raises(ManifestPathUnresolvable):
            asyncio.run(build_diagnosis_context(deps, fault))


def test_build_diagnosis_context_os_uses_hostname_convention() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "NodeExporterDown",
                    "node": "hetzner-worker-1",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "NodeExporterDown"},
        commonLabels={"node": "hetzner-worker-1"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="NodeExporterDown"}',
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(return_value={"content": git_repo_yaml})

    async def nixos_side_effect(tool_name, args=None):
        if tool_name == "get_nix_path":
            return {"content": "infra/nixos/hosts/hetzner-worker-1.nix"}
        return {"content": "nixos-state"}

    mock_nixos = AsyncMock()
    mock_nixos.direct_call_tool = AsyncMock(side_effect=nixos_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": "declared-config"})
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))
    assert ctx.manifest_path == "infra/nixos/hosts/hetzner-worker-1.nix"


def test_build_diagnosis_context_os_happy_path() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "NodeExporterDown",
                    "node": "hetzner-worker-1",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "NodeExporterDown"},
        commonLabels={"node": "hetzner-worker-1"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="NodeExporterDown"}',
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(return_value={"content": git_repo_yaml})
    mock_nixos = AsyncMock()
    mock_nixos.direct_call_tool = AsyncMock(
        side_effect=[
            {"content": "infra/nixos/hosts/hetzner-worker-1.nix"},
            {"content": "live-systemd-status"},
        ]
    )
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(
        return_value={"content": "declared-dry-build"}
    )
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))
    assert ctx.live_yaml == "live-systemd-status"
    assert ctx.declared_yaml == "declared-dry-build"
    assert ctx.manifest_path == "infra/nixos/hosts/hetzner-worker-1.nix"


def test_build_diagnosis_context_os_systemd_unit_fallback() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "NodeExporterDown",
                    "node": "hetzner-worker-1",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "NodeExporterDown"},
        commonLabels={"node": "hetzner-worker-1"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="NodeExporterDown"}',
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(return_value={"content": git_repo_yaml})
    captured_calls: list = []

    async def nixos_side_effect(tool, args):
        captured_calls.append((tool, args))
        return {"content": "state"}

    mock_nixos = AsyncMock()
    mock_nixos.direct_call_tool = AsyncMock(side_effect=nixos_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": "config"})
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    asyncio.run(build_diagnosis_context(deps, fault))
    journal_call = next((c for c in captured_calls if c[0] == "get_journal"), None)
    assert journal_call is not None
    assert journal_call[1].get("host") == "hetzner-worker-1"
    assert "unit" not in journal_call[1], (
        "unit must not be passed when no systemd_unit label"
    )


def test_build_diagnosis_context_os_sysctl_key_surfaces_live_value() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "KernelParameterDrift",
                    "node": "hetzner-worker-1",
                    "sysctl_key": "net.ipv4.ip_forward",
                },
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "KernelParameterDrift"},
        commonLabels={"node": "hetzner-worker-1"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey='{}:{alertname="KernelParameterDrift"}',
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\n"
        "kind: GitRepository\n"
        "metadata:\n"
        "  name: flux-system\n"
        "  namespace: flux-system\n"
        "spec:\n"
        "  ref:\n"
        "    branch: main\n"
    )

    live_sysctl_value = "net.ipv4.ip_forward = 1"

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(return_value={"content": git_repo_yaml})
    captured_calls: list = []

    async def nixos_side_effect(tool, args):
        captured_calls.append((tool, args))
        if tool == "get_nix_path":
            return {"content": "infra/nixos/hosts/hetzner-worker-1.nix"}
        if tool == "get_sysctl":
            return {"content": live_sysctl_value}
        return {"content": "state"}

    mock_nixos = AsyncMock()
    mock_nixos.direct_call_tool = AsyncMock(side_effect=nixos_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(
        return_value={"content": "net.ipv4.ip_forward = 0"}
    )
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))

    sysctl_call = next((c for c in captured_calls if c[0] == "get_sysctl"), None)
    assert sysctl_call is not None, "get_sysctl must be called when sysctl_key present"
    assert sysctl_call[1].get("host") == "hetzner-worker-1"
    assert sysctl_call[1].get("key") == "net.ipv4.ip_forward"

    journal_call = next((c for c in captured_calls if c[0] == "get_journal"), None)
    assert journal_call is None, (
        "get_journal must not be called when sysctl_key present"
    )

    assert ctx.live_yaml == live_sysctl_value


def _make_fault(labels: dict):
    from orchestrator.models import FaultEvent

    return FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": labels,
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={},
        commonLabels={k: v for k, v in labels.items()},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey="{}:{}",
    )


def test_extract_kind_pvc() -> None:
    from diagnosis.context import _extract_k8s_kind_namespace_name

    fault = _make_fault({"persistentvolumeclaim": "data-pvc", "namespace": "storage"})
    kind, ns, name = _extract_k8s_kind_namespace_name(fault)
    assert kind == "PersistentVolumeClaim"
    assert ns == "storage"
    assert name == "data-pvc"


def test_extract_alert_namespace_from_labels() -> None:
    from diagnosis.context import extract_alert_namespace

    fault = _make_fault({"deployment": "api", "namespace": "payments"})
    assert extract_alert_namespace(fault, "default") == "payments"


def test_extract_alert_namespace_falls_back_to_default() -> None:
    from diagnosis.context import extract_alert_namespace

    fault = _make_fault({"node": "worker-1"})
    assert extract_alert_namespace(fault, "default") == "default"


def test_extract_kind_daemonset() -> None:
    from diagnosis.context import _extract_k8s_kind_namespace_name

    fault = _make_fault({"daemonset": "node-exporter", "namespace": "monitoring"})
    kind, ns, name = _extract_k8s_kind_namespace_name(fault)
    assert kind == "DaemonSet"
    assert ns == "monitoring"
    assert name == "node-exporter"


def test_extract_kind_namespace_only_returns_namespace() -> None:
    from diagnosis.context import _extract_k8s_kind_namespace_name

    fault = _make_fault({"alertname": "KubePodNotReady", "namespace": "default"})
    kind, ns, name = _extract_k8s_kind_namespace_name(fault)
    assert kind == "Namespace"
    assert ns == "default"
    assert name == "default"


def test_extract_kind_unknown_raises() -> None:
    from diagnosis.context import (
        ResourceKindUnresolvable,
        _extract_k8s_kind_namespace_name,
    )

    fault = _make_fault({"alertname": "WeirdAlert"})
    with pytest.raises(ResourceKindUnresolvable):
        _extract_k8s_kind_namespace_name(fault)


def test_build_diagnosis_context_constructed_path_missing_raises() -> None:
    """Flux nested topology: resolve_manifest_path failure propagates."""
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {"deployment": "vigil-app", "namespace": "default"},
                "annotations": {},
                "startsAt": "2026-05-01T00:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={},
        commonLabels={"namespace": "default"},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey="{}:{}",
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\nkind: GitRepository\n"
        "metadata:\n  name: flux-system\n  namespace: flux-system\n"
        "spec:\n  ref:\n    branch: chore/eval-cluster-baseline\n"
    )
    live_resource_yaml = (
        "apiVersion: apps/v1\nkind: Deployment\n"
        "metadata:\n  name: vigil-app\n  namespace: default\n"
        "  labels:\n"
        "    kustomize.toolkit.fluxcd.io/name: flux-system\n"
        "    kustomize.toolkit.fluxcd.io/namespace: flux-system\n"
    )
    kust_yaml = (
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\nkind: Kustomization\n"
        "metadata:\n  name: flux-system\n  namespace: flux-system\n"
        "spec:\n  path: clusters/hetzner-eval\n"
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "Deployment":
            return {"content": live_resource_yaml}
        if kind == "Kustomization":
            return {"content": kust_yaml}
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        return {"content": ""}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)

    async def git_side_effect(tool, args):
        if tool == "clone_repo":
            return {"content": "ok"}
        raise RuntimeError("path not found in repository")

    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(side_effect=git_side_effect)
    mock_nixos = AsyncMock()
    mock_flux = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    from diagnosis.context import ManifestPathUnresolvable

    with pytest.raises(ManifestPathUnresolvable):
        asyncio.run(build_diagnosis_context(deps, fault))


def test_build_diagnosis_context_kustomization_apply_error_enrichment() -> None:
    """FluxKustomizationFailed: apply error resolves child resource manifest context."""
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "FluxKustomizationFailed",
                    "kustomization": "cluster-apps",
                    "namespace": "flux-system",
                },
                "annotations": {},
                "startsAt": "1970-01-01T00:00:00Z",
                "endsAt": "",
            }
        ],
        groupLabels={"alertname": "FluxKustomizationFailed"},
        commonLabels={
            "alertname": "FluxKustomizationFailed",
            "namespace": "flux-system",
        },
        commonAnnotations={},
        externalURL="",
        version="4",
        groupKey="eval/FluxKustomizationFailed",
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\nkind: GitRepository\n"
        "metadata:\n  name: flux-system\n  namespace: flux-system\n"
        "spec:\n  ref:\n    branch: chore/eval-cluster-baseline\n"
    )
    kust_status_text = (
        '{"kind": "Kustomization", "namespace": "flux-system", '
        '"name": "cluster-apps", "found": true, "ready": false, '
        '"reason": "ReconciliationFailed", "message": "", "revision": ""}'
    )
    kust_raw_yaml = (
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\nkind: Kustomization\n"
        "metadata:\n  name: cluster-apps\n  namespace: flux-system\n"
        "spec:\n  path: infra/overlays/hetzner/kubernetes/clusters/hetzner/apps\n"
        "status:\n"
        "  conditions:\n"
        "  - reason: ReconciliationFailed\n"
        "    status: 'False'\n"
        '    message: \'Deployment.apps "vigil-app" is invalid: spec.selector: Invalid'
        " value: field is immutable'\n"
    )
    dep_live_yaml = (
        "apiVersion: apps/v1\nkind: Deployment\n"
        "metadata:\n  name: vigil-app\n  namespace: flux-system\n"
        "spec:\n  selector:\n    matchLabels:\n      app: vigil-app\n"
    )
    declared_yaml_content = (
        "apiVersion: apps/v1\nkind: Deployment\n"
        "metadata:\n  name: vigil-app\n  namespace: default\n"
        "spec:\n  selector:\n    matchLabels:\n      app: vigil-app-typo\n"
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        if kind == "Kustomization":
            return {"content": kust_raw_yaml}
        if kind == "Deployment":
            return {"content": dep_live_yaml}
        return {"content": ""}

    async def flux_side_effect(tool, args):
        if tool == "get_kustomization_status":
            return {"content": kust_status_text}
        return {"content": "ok"}

    async def git_side_effect(tool, args):
        if tool == "clone_repo":
            return {"content": "ok"}
        if tool == "resolve_manifest_path":
            return {
                "path": "infra/overlays/hetzner/kubernetes"
                "/clusters/hetzner/apps/vigil-app.yaml"
            }
        if tool == "read_file":
            return {"content": declared_yaml_content}
        return {"content": "ok"}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)
    mock_flux = AsyncMock()
    mock_flux.direct_call_tool = AsyncMock(side_effect=flux_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(side_effect=git_side_effect)
    mock_nixos = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-kust",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))

    _expected_path = (
        "infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"
    )
    assert ctx.manifest_path == _expected_path
    assert "spec.selector" in ctx.live_yaml
    assert "vigil-app-typo" in ctx.declared_yaml
    assert ctx.diff != ""


def test_build_diagnosis_context_kustomization_dependency_fallback() -> None:
    """FluxKustomizationFailed with no extractable apply error falls back to status."""
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "FluxKustomizationFailed",
                    "kustomization": "cluster-apps",
                    "namespace": "flux-system",
                },
                "annotations": {},
                "startsAt": "1970-01-01T00:00:00Z",
                "endsAt": "",
            }
        ],
        groupLabels={},
        commonLabels={"namespace": "flux-system"},
        commonAnnotations={},
        externalURL="",
        version="4",
        groupKey="",
    )

    git_repo_yaml = (
        "apiVersion: source.toolkit.fluxcd.io/v1\nkind: GitRepository\n"
        "metadata:\n  name: flux-system\n  namespace: flux-system\n"
        "spec:\n  ref:\n    branch: main\n"
    )
    kust_raw_yaml = (
        "apiVersion: kustomize.toolkit.fluxcd.io/v1\nkind: Kustomization\n"
        "metadata:\n  name: cluster-apps\n  namespace: flux-system\n"
        "status:\n"
        "  conditions:\n"
        "  - reason: DependencyNotReady\n"
        "    status: 'False'\n"
        "    message: \"dependency 'flux-system/cluster-infrastructure'"
        ' is not ready"\n'
    )
    _dep_msg = "dependency 'flux-system/cluster-infrastructure' is not ready"
    kust_status_text = (
        '{"kind": "Kustomization", "namespace": "flux-system", '
        '"name": "cluster-apps", "found": true, "ready": false, '
        f'"reason": "DependencyNotReady", "message": "{_dep_msg}", '
        '"revision": ""}'
    )

    async def kubectl_side_effect(tool, args):
        kind = args.get("kind", "")
        if kind == "GitRepository":
            return {"content": git_repo_yaml}
        if kind == "Kustomization":
            return {"content": kust_raw_yaml}
        return {"content": ""}

    async def flux_side_effect(tool, args):
        if tool == "get_kustomization_status":
            return {"content": kust_status_text}
        return {"content": "ok"}

    mock_kubectl = AsyncMock()
    mock_kubectl.direct_call_tool = AsyncMock(side_effect=kubectl_side_effect)
    mock_flux = AsyncMock()
    mock_flux.direct_call_tool = AsyncMock(side_effect=flux_side_effect)
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    mock_nixos = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        run_id="test-kust-dep",
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
        flux_mcp=mock_flux,
    )

    ctx = asyncio.run(build_diagnosis_context(deps, fault))

    assert ctx.manifest_path is None
    assert "cluster-apps" in ctx.live_yaml


def _canned_context_for_msg():
    from diagnosis.context import DiagnosisContext

    return DiagnosisContext(
        source_branch="main",
        manifest_path="apps/vigil-app.yaml",
        live_yaml="live: yaml",
        declared_yaml="declared: yaml",
        diff="",
    )


def _canned_fault_for_msg():
    from orchestrator.models import FaultEvent

    return FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[],
        groupLabels={},
        commonLabels={},
        commonAnnotations={},
        externalURL="http://alertmanager:9093",
        version="4",
        groupKey="{}",
    )


def test_build_user_message_includes_retry_hint_prefix() -> None:
    hint = (
        "Attempt 2 of 3: prior recommended_action=git_commit_k8s. "
        "Cluster still degraded after settle."
    )
    msg = _build_user_message(_canned_fault_for_msg(), _canned_context_for_msg(), hint)
    assert msg.startswith("Retry signal:")
    assert hint in msg
    assert "Diagnose fault." in msg


def test_build_user_message_without_hint_has_no_retry_block() -> None:
    msg = _build_user_message(
        _canned_fault_for_msg(), _canned_context_for_msg(), retry_hint=None
    )
    assert "Retry signal:" not in msg
    assert msg.startswith("Diagnose fault.")


async def test_run_diagnosis_converts_budget_abort_despite_aexit_remask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Budget exhaustion must surface as DiagnosisRequestBudgetExceeded.

    Reproduces the field failure: pydantic-ai's iterator context manager re-raises
    the original UsageLimitExceeded from __aexit__, which would mask the converted
    DiagnosisRequestBudgetExceeded if the conversion ran inside the async with.
    """
    from unittest.mock import AsyncMock, MagicMock

    from diagnosis.models import DiagnosisRequestBudgetExceeded
    from pydantic_ai.exceptions import UsageLimitExceeded
    from pydantic_ai.usage import RunUsage

    monkeypatch.setattr(_diag_module.trace, "write_trace", lambda *a, **k: None)

    limit_exc = UsageLimitExceeded("request_limit (25) exceeded")

    class _FakeAgentRun:
        usage = RunUsage(input_tokens=10, output_tokens=2)

        def all_messages(self):
            return ["partial"]

        def __aiter__(self):
            return self

        async def __anext__(self):
            raise limit_exc

    class _FakeIterCM:
        def __init__(self) -> None:
            self._run = _FakeAgentRun()

        async def __aenter__(self):
            return self._run

        async def __aexit__(self, exc_type, exc, tb):
            raise limit_exc

    monkeypatch.setattr(
        _diag_module.diagnosis_agent,
        "iter",
        MagicMock(return_value=_FakeIterCM()),
    )

    deps = DiagnosisDeps(
        run_id="test-run",
        kubectl_mcp=AsyncMock(),
        nixos_mcp=AsyncMock(),
        git_mcp=AsyncMock(),
        flux_mcp=AsyncMock(),
    )

    with pytest.raises(DiagnosisRequestBudgetExceeded):
        await run_diagnosis(deps, _canned_fault_for_msg(), _canned_context_for_msg())
