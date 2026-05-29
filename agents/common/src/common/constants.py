"""Shared runtime constants for vigil agents."""

import os

GIT_COMMIT_BUDGET: int = int(os.environ.get("GIT_COMMIT_BUDGET", "1"))

CIRCUIT_BREAKER_THRESHOLD: int = int(
    os.environ.get("CIRCUIT_BREAKER_THRESHOLD", "3")
)

_DEFAULT_PROTECTED_BRANCHES = "main,master"

PROTECTED_BRANCHES: frozenset[str] = frozenset(
    branch.strip()
    for branch in os.environ.get(
        "VIGIL_PROTECTED_BRANCHES", _DEFAULT_PROTECTED_BRANCHES
    ).split(",")
    if branch.strip()
)

DIAGNOSIS_KUBECTL_READ_TOOLS: frozenset[str] = frozenset(
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
    }
)

DIAGNOSIS_FLUX_READ_TOOLS: frozenset[str] = frozenset(
    {
        "get_kustomization_status",
        "get_gitrepository_status",
    }
)

DIAGNOSIS_NIXOS_READ_TOOLS: frozenset[str] = frozenset(
    {
        "get_generations",
        "get_journal",
        "get_systemd_status",
        "get_nix_path",
        "dry_build",
    }
)

DIAGNOSIS_GIT_READ_TOOLS: frozenset[str] = frozenset(
    {
        "clone_repo",
        "read_file",
        "resolve_manifest_path",
    }
)
