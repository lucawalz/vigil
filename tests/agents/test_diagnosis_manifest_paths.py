from __future__ import annotations

import pytest
from diagnosis.manifest_paths import (
    ManifestPathError,
    lookup_k8s_manifest_path,
    lookup_os_manifest_path,
)


def test_lookup_k8s_manifest_path_returns_path() -> None:
    kust_yaml = "kind: Kustomization\nspec:\n  path: kubernetes/apps\n"
    result = lookup_k8s_manifest_path(kust_yaml, "vigil-app")
    assert result == "kubernetes/apps/vigil-app.yaml"


def test_lookup_k8s_manifest_path_strips_leading_slash() -> None:
    kust_yaml = "kind: Kustomization\nspec:\n  path: /kubernetes/apps\n"
    result = lookup_k8s_manifest_path(kust_yaml, "vigil-app")
    assert result == "kubernetes/apps/vigil-app.yaml"


def test_lookup_k8s_manifest_path_raises_for_non_kustomization() -> None:
    yaml_str = "kind: Deployment\nmetadata:\n  name: vigil-app\n"
    with pytest.raises(ManifestPathError):
        lookup_k8s_manifest_path(yaml_str, "vigil-app")


def test_lookup_k8s_manifest_path_raises_when_spec_path_missing() -> None:
    kust_yaml = "kind: Kustomization\nspec:\n  interval: 5m\n"
    with pytest.raises(ManifestPathError):
        lookup_k8s_manifest_path(kust_yaml, "vigil-app")


def test_lookup_k8s_manifest_path_raises_on_invalid_yaml() -> None:
    with pytest.raises(ManifestPathError):
        lookup_k8s_manifest_path("}{invalid yaml}{", "vigil-app")


def test_lookup_os_manifest_path_uses_hostname_convention() -> None:
    result = lookup_os_manifest_path("hetzner-1")
    assert result == "infra/nixos/hosts/hetzner-1/default.nix"


def test_lookup_os_manifest_path_pure_string() -> None:
    result = lookup_os_manifest_path("any-host")
    assert result == "infra/nixos/hosts/any-host/default.nix"
