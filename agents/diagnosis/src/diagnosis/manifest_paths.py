"""Manifest path resolution via Kustomization YAML or hostname convention."""

from __future__ import annotations

import yaml


class ManifestPathError(Exception):
    """Raised when manifest path cannot be resolved for the given resource."""


def lookup_k8s_manifest_path(kustomization_yaml: str, resource_name: str) -> str:
    try:
        data = yaml.safe_load(kustomization_yaml)
    except yaml.YAMLError as exc:
        raise ManifestPathError(f"YAML parse error: {exc}") from exc

    if not isinstance(data, dict) or data.get("kind") != "Kustomization":
        raise ManifestPathError("YAML is not a Kustomization object")

    spec_path = (data.get("spec") or {}).get("path")
    if not spec_path:
        raise ManifestPathError("Kustomization spec.path is absent or empty")

    spec_path = spec_path.removeprefix("./").lstrip("/")
    return f"{spec_path}/{resource_name}.yaml"


def lookup_os_manifest_path(hostname: str) -> str:
    return f"infra/nixos/hosts/{hostname}/default.nix"
