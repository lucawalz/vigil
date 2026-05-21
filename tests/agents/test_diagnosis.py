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
from diagnosis.agent import diagnosis_agent, run_diagnosis
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


def test_run_diagnosis_enforces_usage_limit_25() -> None:
    """25-iteration ceiling via DIAGNOSIS_REQUEST_LIMIT env var (default 25)."""
    source = inspect.getsource(run_diagnosis)
    assert 'os.environ.get("DIAGNOSIS_REQUEST_LIMIT", "25")' in source


def test_diagnosis_system_prompt_forbids_symptom_naming() -> None:
    """System prompt must never name a symptom as root cause."""
    source = inspect.getsource(_diag_module)
    has_symptom_clause = any(
        term in source for term in ("CrashLoopBackOff", "ImagePullBackOff", "OOMKilled")
    )
    assert has_symptom_clause, "System prompt must forbid K8s symptoms as root causes"


def test_run_diagnosis_signature_accepts_diagnosis_deps() -> None:
    """run_diagnosis(deps, fault, model=None) -> tuple."""
    sig = inspect.signature(run_diagnosis)
    params = list(sig.parameters.values())
    assert len(params) == 3
    assert params[0].name == "deps"
    ann = params[0].annotation
    assert ann is DiagnosisDeps or (isinstance(ann, str) and "DiagnosisDeps" in ann)


def test_run_diagnosis_returns_tuple_with_usage() -> None:
    """Orchestrator needs usage tuple for token aggregation."""
    source = inspect.getsource(run_diagnosis)
    assert "result.usage" in source
    assert "result.all_messages()" in source
    assert "return result.output, result.usage, result.all_messages()" in source


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
        live_observed="n/a (manifest path unresolvable)",
        declared_observed="n/a (manifest path unresolvable)",
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
        "live_observed": "image=nginx:bad-tag-v9",
        "declared_observed": "image=nginx:stable",
        "recommended_action": "flux_reconcile",
        "confidence": 0.95,
        **overrides,
    }


def test_drift_classification_validator_rejects_live_drift_with_git_commit() -> None:
    import pytest

    with pytest.raises(Exception, match="live_only_drift"):
        DiagnosisReport(**_base_report_kwargs(recommended_action="git_commit_k8s"))


def test_drift_classification_validator_rejects_declared_drift_with_flux_reconcile() -> None:
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
        DiagnosisReport(**_base_report_kwargs(drift_classification=dc, recommended_action=action))


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
    assert "def lookup_k8s_manifest_path" in source
    assert "def lookup_os_manifest_path" in source


def test_kubectl_write_tools_is_empty_frozenset() -> None:
    source = inspect.getsource(_diag_module)
    assert "_kubectl_write_tools = frozenset()" in source


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


def test_proposed_patch_allows_none_patch_body() -> None:
    from diagnosis.models import ProposedPatch

    patch = ProposedPatch(
        resource_kind="Pod",
        resource_namespace="default",
        resource_name="foo",
    )
    assert patch.patch_body is None


# --- DiagnosisContext tests ---


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
    }
    assert fields["source_branch"].type in (str, "str")
    assert fields["manifest_path"].type in ("str | None", "Optional[str]")
    assert fields["live_yaml"].type in (str, "str")
    assert fields["declared_yaml"].type in (str, "str")
    assert fields["diff"].type in (str, "str")


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
        alerts=[{
            "status": "firing",
            "labels": {
                "alertname": "KubePodImagePullBackOff",
                "namespace": "default",
                "deployment": "vigil-app",
            },
            "annotations": {},
            "startsAt": "2026-05-01T00:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }],
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
    mock_git.direct_call_tool = AsyncMock(return_value={"content": declared_yaml_content})
    mock_nixos = AsyncMock()

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
    )

    ctx = asyncio.get_event_loop().run_until_complete(
        build_diagnosis_context(deps, fault)
    )
    assert ctx.live_yaml == live_resource_yaml
    assert ctx.declared_yaml == declared_yaml_content
    assert "--- live" in ctx.diff or ctx.diff == ""
    assert ctx.source_branch == "main"
    assert ctx.manifest_path is not None


def test_build_diagnosis_context_manifest_path_unresolvable() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import ManifestPathUnresolvable, build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[{
            "status": "firing",
            "labels": {
                "alertname": "KubePodCrash",
                "namespace": "default",
                "deployment": "unmanaged-app",
            },
            "annotations": {},
            "startsAt": "2026-05-01T00:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }],
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

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
    )

    with pytest.raises(ManifestPathUnresolvable):
        asyncio.get_event_loop().run_until_complete(
            build_diagnosis_context(deps, fault)
        )


def test_build_diagnosis_context_os_uses_hostname_convention() -> None:
    import asyncio
    from unittest.mock import AsyncMock

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[{
            "status": "firing",
            "labels": {
                "alertname": "NodeExporterDown",
                "node": "hetzner-worker-1",
            },
            "annotations": {},
            "startsAt": "2026-05-01T00:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }],
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
    mock_nixos.direct_call_tool = AsyncMock(return_value={"content": "nixos-state"})
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": "declared-config"})

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
    )

    ctx = asyncio.get_event_loop().run_until_complete(
        build_diagnosis_context(deps, fault)
    )
    assert ctx.manifest_path == "infra/nixos/hosts/hetzner-worker-1.nix"


def test_build_diagnosis_context_os_happy_path() -> None:
    import asyncio
    from unittest.mock import AsyncMock, call

    from diagnosis.context import build_diagnosis_context
    from orchestrator.models import FaultEvent

    fault = FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[{
            "status": "firing",
            "labels": {
                "alertname": "NodeExporterDown",
                "node": "hetzner-worker-1",
            },
            "annotations": {},
            "startsAt": "2026-05-01T00:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }],
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
    mock_nixos.direct_call_tool = AsyncMock(side_effect=[
        {"content": "live-systemd-status"},
        {"content": "declared-dry-build"},
    ])
    mock_git = AsyncMock()
    mock_git.direct_call_tool = AsyncMock(return_value={"content": "declared-config"})

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
    )

    ctx = asyncio.get_event_loop().run_until_complete(
        build_diagnosis_context(deps, fault)
    )
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
        alerts=[{
            "status": "firing",
            "labels": {
                "alertname": "NodeExporterDown",
                "node": "hetzner-worker-1",
            },
            "annotations": {},
            "startsAt": "2026-05-01T00:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
        }],
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

    from diagnosis.models import DiagnosisDeps

    deps = DiagnosisDeps(
        kubectl_mcp=mock_kubectl,
        nixos_mcp=mock_nixos,
        git_mcp=mock_git,
    )

    asyncio.get_event_loop().run_until_complete(build_diagnosis_context(deps, fault))
    systemd_call = next(
        (c for c in captured_calls if c[0] == "get_systemd_status"), None
    )
    assert systemd_call is not None
    assert systemd_call[1].get("unit") == "vigil-auto-reconcile.service"
