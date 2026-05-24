from __future__ import annotations

from diagnosis.manifest_paths import lookup_os_manifest_path


def test_lookup_os_manifest_path_uses_hostname_convention() -> None:
    result = lookup_os_manifest_path("hetzner-1")
    assert result == "infra/nixos/hosts/hetzner-1/default.nix"


def test_lookup_os_manifest_path_pure_string() -> None:
    result = lookup_os_manifest_path("any-host")
    assert result == "infra/nixos/hosts/any-host/default.nix"
