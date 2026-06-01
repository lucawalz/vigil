"""Diagnosis tool-scope contract: only allow-listed read tools reach the LLM."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Provide test env vars BEFORE importing diagnosis.agent (build_model() reads them).
os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")

from common.constants import (
    DIAGNOSIS_FLUX_READ_TOOLS,
    DIAGNOSIS_GIT_READ_TOOLS,
    DIAGNOSIS_KUBECTL_READ_TOOLS,
    DIAGNOSIS_NIXOS_READ_TOOLS,
)
from diagnosis.agent import is_diagnosis_tool_allowed

_KUBECTL_ALL_TOOLS = frozenset(
    {
        "get_nodes",
        "get_pods",
        "describe_pod",
        "get_logs",
        "rollout_status",
        "get_events",
        "describe_node",
        "get_taints",
        "get_resource_yaml",
        "delete_resource",
    }
)

_FLUX_ALL_TOOLS = frozenset(
    {
        "reconcile_kustomization",
        "get_kustomization_status",
        "get_gitrepository_status",
    }
)

_NIXOS_ALL_TOOLS = frozenset(
    {
        "get_generations",
        "stage_generation",
        "commit_generation",
        "rebuild_test",
        "get_journal",
        "get_systemd_status",
        "get_sysctl",
        "etcd_snapshot_save",
        "get_nix_path",
        "dry_build",
        "trigger_reconcile",
    }
)

_GIT_ALL_TOOLS = frozenset(
    {
        "clone_repo",
        "create_branch",
        "write_manifest",
        "commit_files",
        "push_branch",
        "create_pr",
        "get_pr_status",
        "wait_for_gate",
        "revert_commit",
        "close_pr",
        "delete_branch",
        "read_file",
        "resolve_manifest_path",
    }
)


@dataclass(frozen=True)
class _StubToolDef:
    name: str


def _exposed(
    server_tools: frozenset[str],
    allowed_tools: frozenset[str],
    blocked_tools: frozenset[str] = frozenset(),
) -> frozenset[str]:
    tool_defs = [_StubToolDef(name) for name in server_tools]
    return frozenset(
        td.name
        for td in tool_defs
        if is_diagnosis_tool_allowed(td.name, allowed_tools, blocked_tools)
    )


def test_kubectl_exposes_exactly_the_allow_list() -> None:
    assert (
        _exposed(_KUBECTL_ALL_TOOLS, DIAGNOSIS_KUBECTL_READ_TOOLS)
        == DIAGNOSIS_KUBECTL_READ_TOOLS
    )


def test_flux_exposes_exactly_the_allow_list() -> None:
    exposed = _exposed(_FLUX_ALL_TOOLS, DIAGNOSIS_FLUX_READ_TOOLS)
    assert exposed == DIAGNOSIS_FLUX_READ_TOOLS


def test_nixos_exposes_exactly_the_allow_list() -> None:
    assert (
        _exposed(_NIXOS_ALL_TOOLS, DIAGNOSIS_NIXOS_READ_TOOLS)
        == DIAGNOSIS_NIXOS_READ_TOOLS
    )


def test_git_exposes_exactly_the_allow_list() -> None:
    exposed = _exposed(_GIT_ALL_TOOLS, DIAGNOSIS_GIT_READ_TOOLS)
    assert exposed == DIAGNOSIS_GIT_READ_TOOLS


def test_all_git_write_tools_are_filtered_out() -> None:
    write_tools = _GIT_ALL_TOOLS - DIAGNOSIS_GIT_READ_TOOLS
    exposed = _exposed(_GIT_ALL_TOOLS, DIAGNOSIS_GIT_READ_TOOLS)
    assert write_tools & exposed == frozenset()
    for tool in (
        "commit_files",
        "push_branch",
        "create_pr",
        "write_manifest",
        "create_branch",
        "revert_commit",
        "close_pr",
        "delete_branch",
    ):
        assert tool not in exposed


def test_side_effecting_tools_are_filtered_out() -> None:
    assert "delete_resource" not in _exposed(
        _KUBECTL_ALL_TOOLS, DIAGNOSIS_KUBECTL_READ_TOOLS
    )
    assert "reconcile_kustomization" not in _exposed(
        _FLUX_ALL_TOOLS, DIAGNOSIS_FLUX_READ_TOOLS
    )
    nixos_exposed = _exposed(_NIXOS_ALL_TOOLS, DIAGNOSIS_NIXOS_READ_TOOLS)
    for tool in (
        "stage_generation",
        "commit_generation",
        "etcd_snapshot_save",
        "rebuild_test",
        "trigger_reconcile",
    ):
        assert tool not in nixos_exposed


def test_unknown_tool_is_filtered_out_fail_safe() -> None:
    assert not is_diagnosis_tool_allowed(
        "newly_added_write_tool", DIAGNOSIS_KUBECTL_READ_TOOLS, frozenset()
    )
    assert not is_diagnosis_tool_allowed(
        "newly_added_write_tool", DIAGNOSIS_GIT_READ_TOOLS, frozenset()
    )


def test_blocked_tools_override_allow_list() -> None:
    blocked = frozenset({"get_logs"})
    exposed = _exposed(_KUBECTL_ALL_TOOLS, DIAGNOSIS_KUBECTL_READ_TOOLS, blocked)
    assert "get_logs" not in exposed
    assert exposed == DIAGNOSIS_KUBECTL_READ_TOOLS - blocked
