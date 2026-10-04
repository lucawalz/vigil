import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures" / "hcloud.json"
CUTOFF = datetime(2026, 10, 3, 12, tzinfo=UTC)
NEW_RUN = "202"
EXPIRED_RUN = "101"

_spec = importlib.util.spec_from_file_location(
    "hcloud_sweep", REPO / "scripts" / "hcloud_sweep.py"
)
assert _spec is not None and _spec.loader is not None
hcloud_sweep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hcloud_sweep)


class RecordedApi:
    def __init__(self) -> None:
        self.responses = json.loads(FIXTURE.read_text())
        self.deleted: list[str] = []

    def __call__(self, method: str, path: str) -> dict:
        if method == "DELETE":
            self.deleted.append(path)
            return {}
        url = urlparse(path)
        kind = url.path
        query = parse_qs(url.query)
        wanted = dict(pair.split("=") for pair in query["label_selector"][0].split(","))
        response = self.responses[kind][int(query["page"][0]) - 1]
        items = [
            item
            for item in response[kind]
            if wanted.items() <= item["labels"].items()
            and f"{kind}/{item['id']}" not in self.deleted
        ]
        return {kind: items, "meta": response["meta"]}


def _dry_run_lines(keep: frozenset[str] = frozenset()) -> list[str]:
    lines: list[str] = []
    count = hcloud_sweep.sweep(
        RecordedApi(),
        run=None,
        cutoff=CUTOFF,
        dry_run=True,
        keep=keep,
        out=lines.append,
    )
    assert count == len(lines)
    return lines


def test_dry_run_lists_expired_runs_and_old_unlabelled_resources() -> None:
    assert _dry_run_lines() == [
        "would delete servers 4711 k8s-101-k8s-s1-control-plane-1",
        "would delete servers 4713 k8s-101-k8s-s1-worker-1",
        "would delete images 9001 vigil-nixos-control-plane-1-abc",
        "would delete networks 31 vigil-eval-k8s-101-k8s-s1",
        "would delete ssh_keys 51 vigil-operator-k8s-101-k8s-s1",
        "would delete ssh_keys 52 vigil-unlabelled-old",
    ]


def test_age_mode_keeps_every_resource_of_a_run_with_a_recent_one() -> None:
    lines = _dry_run_lines()
    assert not [line for line in lines if " 9002 " in line or " 4721 " in line]


def test_age_mode_keeps_an_expired_run_that_is_still_in_progress() -> None:
    assert _dry_run_lines(keep=frozenset({EXPIRED_RUN})) == [
        "would delete ssh_keys 52 vigil-unlabelled-old",
    ]


def test_dry_run_sends_no_delete() -> None:
    api = RecordedApi()
    hcloud_sweep.sweep(api, run=None, cutoff=CUTOFF, dry_run=True, out=print)
    assert api.deleted == []


def test_run_scope_deletes_that_run_only_and_servers_first() -> None:
    api = RecordedApi()
    hcloud_sweep.sweep(
        api, run=NEW_RUN, cutoff=None, dry_run=False, out=lambda _line: None
    )
    assert api.deleted == ["servers/4712", "firewalls/71"]
