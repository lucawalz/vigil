"""Manifest path resolution via hostname convention."""

from __future__ import annotations


def lookup_os_manifest_path(hostname: str) -> str:
    return f"infra/nixos/hosts/{hostname}/default.nix"
