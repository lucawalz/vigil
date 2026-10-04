from __future__ import annotations

import json
from dataclasses import dataclass

from vigil_lab.proc import LabError, run

SSH_FORWARD_BASE_PORT = 2200
CONTROL_PLANE_ROLE = "control-plane"
WORKER_ROLE = "worker"


@dataclass(frozen=True)
class LabHost:
    name: str
    role: str
    index: int
    flake_attrs: dict[str, str]

    @property
    def ssh_port(self) -> int:
        return SSH_FORWARD_BASE_PORT + self.index

    def flake_attr(self, system: str) -> str:
        try:
            return self.flake_attrs[system]
        except KeyError:
            raise LabError(
                f"{self.name} has no lab configuration for {system}"
            ) from None


@dataclass(frozen=True)
class AddressPlan:
    hosts: tuple[LabHost, ...]

    @property
    def control_plane(self) -> LabHost:
        return next(h for h in self.hosts if h.role == CONTROL_PLANE_ROLE)

    @property
    def workers(self) -> tuple[LabHost, ...]:
        return tuple(h for h in self.hosts if h.role == WORKER_ROLE)


def parse_address_plan(raw: str) -> AddressPlan:
    hosts = (
        LabHost(
            name=name,
            role=entry["role"],
            index=entry["index"],
            flake_attrs=entry["labFlakeAttrs"],
        )
        for name, entry in json.loads(raw)["hosts"].items()
        if "labFlakeAttrs" in entry
    )
    return AddressPlan(hosts=tuple(sorted(hosts, key=lambda host: host.index)))


def load_address_plan(flake: str) -> AddressPlan:
    return parse_address_plan(run(["nix", "eval", "--json", f"{flake}#lib.addresses"]))
