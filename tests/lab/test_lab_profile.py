import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FLAKE = REPO_ROOT / "infra" / "nixos"
FIXTURE = Path(__file__).parent / "fixtures" / "addresses.json"
HUB_INTERFACE = "hub0"
HUB_LINK_UNIT = "10-vigil-hub.link"
PROFILE_PROBE = f"""c: {{
  link = c.systemd.network.units."{HUB_LINK_UNIT}".text;
  installed = c.environment.etc."systemd/network/{HUB_LINK_UNIT}".enable;
  addresses = map (a: a.address) c.networking.interfaces.{HUB_INTERFACE}.ipv4.addresses;
  flags = c.services.k3s.extraFlags;
}}"""

pytestmark = pytest.mark.skipif(
    shutil.which("nix") is None, reason="nix is not installed"
)


def _nix_eval(attr: str, *extra: str) -> object:
    result = subprocess.run(
        ["nix", "eval", "--json", f"{FLAKE}#{attr}", *extra],
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "NIX_CONFIG": "builders ="},
    )
    return json.loads(result.stdout)


def test_flake_address_plan_matches_the_fixture() -> None:
    assert _nix_eval("lib.addresses") == json.loads(FIXTURE.read_text())


@pytest.mark.parametrize(
    ("host", "attr"),
    [
        ("vigil-control-plane-1", "vigil-control-plane-1-lab-x86_64"),
        ("vigil-control-plane-1", "vigil-control-plane-1-lab-aarch64"),
        ("vigil-worker-1", "vigil-worker-1-lab-x86_64"),
    ],
)
def test_lab_profile_names_the_hub_interface_by_its_mac(host: str, attr: str) -> None:
    planned = json.loads(FIXTURE.read_text())["hosts"][host]
    profile = _nix_eval(f"nixosConfigurations.{attr}.config", "--apply", PROFILE_PROBE)
    assert isinstance(profile, dict)
    assert profile["installed"]
    assert f"MACAddress={planned['hubMac']}" in profile["link"]
    assert f"Name={HUB_INTERFACE}" in profile["link"]
    assert profile["addresses"] == [planned["ip"]]
    assert f"--flannel-iface={HUB_INTERFACE}" in profile["flags"]
