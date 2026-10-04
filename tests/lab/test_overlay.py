from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
LAB = REPO / "infra/overlays/lab/kubernetes/clusters/lab"
HEALTH_GATE_KUSTOMIZATIONS = {"cluster-infrastructure", "cluster-apps"}


def _flux_kustomizations() -> dict[str, dict]:
    paths = sorted((LAB / "config").glob("*.yaml"))
    docs = [yaml.safe_load(p.read_text()) for p in paths]
    return {doc["metadata"]["name"]: doc for doc in docs}


def test_lab_cluster_defines_the_kustomizations_the_health_gate_waits_for() -> None:
    assert HEALTH_GATE_KUSTOMIZATIONS <= set(_flux_kustomizations())


def test_every_flux_path_exists_in_the_repository() -> None:
    for name, doc in _flux_kustomizations().items():
        assert (REPO / doc["spec"]["path"]).is_dir(), name


def test_apps_reuse_the_hetzner_app_manifests() -> None:
    apps = _flux_kustomizations()["cluster-apps"]["spec"]
    assert apps["path"] == "./infra/overlays/hetzner/kubernetes/clusters/hetzner/apps"
    assert apps["dependsOn"] == [{"name": "cluster-infrastructure"}]


def test_infrastructure_substitutes_the_lab_webhook_url() -> None:
    spec = _flux_kustomizations()["cluster-infrastructure"]["spec"]
    assert spec["postBuild"]["substituteFrom"] == [
        {"kind": "ConfigMap", "name": "vigil-lab-settings"}
    ]
    values = yaml.safe_load((LAB / "infrastructure/values-lab.yaml").read_text())
    config = values["alertmanager"]["config"]
    assert config["route"] == {"receiver": "vigil-webhook", "routes": []}
    assert config["receivers"][0]["webhook_configs"][0]["url"] == "${VIGIL_WEBHOOK_URL}"
    assert values["prometheus"]["enabled"] is False
