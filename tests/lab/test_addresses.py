import json
from pathlib import Path

import pytest
from vigil_lab.addresses import AddressPlan, parse_address_plan
from vigil_lab.proc import LabError

FIXTURE = Path(__file__).parent / "fixtures" / "addresses.json"
CONTROL_PLANE_SSH_PORT = 2210
WORKER_1_SSH_PORT = 2211


def _plan() -> AddressPlan:
    return parse_address_plan(FIXTURE.read_text())


def test_plan_keeps_only_lab_hosts_in_index_order() -> None:
    assert [h.name for h in _plan().hosts] == [
        "vigil-control-plane-1",
        "vigil-worker-1",
        "vigil-worker-2",
    ]


def test_hosts_carry_the_ssh_forward_and_flake_attributes() -> None:
    worker = _plan().workers[0]
    assert (worker.name, worker.ssh_port) == ("vigil-worker-1", WORKER_1_SSH_PORT)
    assert worker.flake_attr("aarch64-linux") == "vigil-worker-1-lab-aarch64"
    assert _plan().control_plane.ssh_port == CONTROL_PLANE_SSH_PORT


def test_hosts_carry_the_hub_mac_from_the_plan() -> None:
    assert [h.hub_mac for h in _plan().hosts] == [
        "52:54:00:fa:00:10",
        "52:54:00:fa:00:11",
        "52:54:00:fa:00:12",
    ]


def test_lab_host_without_a_hub_mac_names_the_host() -> None:
    raw = json.loads(FIXTURE.read_text())
    del raw["hosts"]["vigil-worker-2"]["hubMac"]
    with pytest.raises(LabError, match="vigil-worker-2"):
        parse_address_plan(json.dumps(raw))


def test_unknown_system_names_the_host() -> None:
    with pytest.raises(LabError, match="vigil-worker-1"):
        _plan().workers[0].flake_attr("riscv64-linux")
