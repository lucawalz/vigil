"""Deterministic (kind, namespace, name) -> repo-relative manifest path lookup."""

from __future__ import annotations

_MANIFEST_PATHS: dict[tuple[str, str, str], str] = {
    ("Deployment", "default", "vigil-app"): (
        "infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"
    ),
}


def lookup_manifest_path(kind: str, namespace: str, name: str) -> str:
    path = _MANIFEST_PATHS.get((kind, namespace, name))
    if path is None:
        return f"unknown resource: {kind}/{namespace}/{name}"
    return path
