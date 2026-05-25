"""Static RBAC contract: eval-runner ClusterRole must cover context pre-fetch verbs."""

from __future__ import annotations

from pathlib import Path

import yaml

_CLUSTERROLE_PATH = (
    Path(__file__).parents[2] / "infra/kubernetes/rbac/eval-runner-clusterrole.yaml"
)

_REQUIRED_VERBS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("", "pods", "get"),
        ("", "pods", "list"),
        ("", "events", "list"),
        ("", "resourcequotas", "get"),
        ("", "resourcequotas", "list"),
        ("", "limitranges", "list"),
        ("apps", "deployments", "get"),
        ("apps", "statefulsets", "get"),
        ("apps", "replicasets", "get"),
        ("networking.k8s.io", "networkpolicies", "list"),
        ("kustomize.toolkit.fluxcd.io", "kustomizations", "get"),
        ("source.toolkit.fluxcd.io", "gitrepositories", "get"),
    }
)

_ALL_VERBS = frozenset({"get", "list", "watch", "create", "patch", "update", "delete"})


def _granted_verbs() -> frozenset[tuple[str, str, str]]:
    data = yaml.safe_load(_CLUSTERROLE_PATH.read_text())
    granted: set[tuple[str, str, str]] = set()
    for rule in data.get("rules", []):
        groups = rule.get("apiGroups", [])
        resources = rule.get("resources", [])
        verbs = rule.get("verbs", [])
        expand = _ALL_VERBS if "*" in verbs else frozenset(verbs)
        for group in groups:
            for resource in resources:
                for verb in expand:
                    granted.add((group, resource, verb))
    return frozenset(granted)


def test_eval_runner_clusterrole_grants_all_context_prefetch_verbs() -> None:
    missing = _REQUIRED_VERBS - _granted_verbs()
    assert not missing, (
        "eval-runner ClusterRole missing verbs for context pre-fetch: "
        f"{sorted(missing)}"
    )
