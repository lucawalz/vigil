from __future__ import annotations

from pathlib import Path

from diagnosis.manifest_paths import _MANIFEST_PATHS, lookup_manifest_path


def test_lookup_manifest_path_returns_path_for_vigil_app_deployment() -> None:
    assert (
        lookup_manifest_path("Deployment", "default", "vigil-app")
        == "infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"
    )


def test_lookup_manifest_path_returns_error_for_unknown_resource() -> None:
    assert (
        lookup_manifest_path("Deployment", "default", "unknown-app")
        == "unknown resource: Deployment/default/unknown-app"
    )


def test_lookup_manifest_path_returns_error_for_wrong_kind() -> None:
    assert (
        lookup_manifest_path("StatefulSet", "default", "vigil-app")
        == "unknown resource: StatefulSet/default/vigil-app"
    )


def test_known_path_exists_on_disk() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    path = lookup_manifest_path("Deployment", "default", "vigil-app")
    assert (repo_root / path).exists()


def test_manifest_paths_table_is_non_empty_dict() -> None:
    assert isinstance(_MANIFEST_PATHS, dict) and len(_MANIFEST_PATHS) >= 1


def test_lookup_redis_master_returns_helmrelease_path() -> None:
    result = lookup_manifest_path("StatefulSet", "default", "redis-master")
    assert result.endswith("redis/helmrelease.yaml"), (
        f"expected path ending in 'redis/helmrelease.yaml', got {result!r}"
    )


def test_lookup_postgresql_returns_unknown_resource() -> None:
    result = lookup_manifest_path("StatefulSet", "default", "postgresql")
    assert result.startswith("unknown resource"), (
        f"expected 'unknown resource' prefix, got {result!r}"
    )
