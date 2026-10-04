import argparse
import json
import os
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

API_URL = "https://api.hetzner.cloud/v1"
MANAGED_SELECTOR = "vigil-managed=true"
RUN_LABEL = "vigil-run"
DEFAULT_MAX_AGE_HOURS = 12
PAGE_SIZE = 50
HTTP_TIMEOUT_S = 30
SERVER_GONE_TIMEOUT_S = 300
SERVER_GONE_POLL_S = 10
SERVERS = "servers"
RESOURCE_KINDS = (SERVERS, "images", "networks", "ssh_keys", "firewalls")
KIND_FILTERS = {"images": {"type": "snapshot"}}

Request = Callable[[str, str], dict]


def http_request(token: str) -> Request:
    def request(method: str, path: str) -> dict:
        call = urllib.request.Request(
            f"{API_URL}/{path}",
            method=method,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(call, timeout=HTTP_TIMEOUT_S) as response:
            body = response.read()
        return json.loads(body) if body else {}

    return request


def list_resources(request: Request, kind: str, selector: str) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page:
        query = {
            "label_selector": selector,
            "per_page": PAGE_SIZE,
            "page": page,
            **KIND_FILTERS.get(kind, {}),
        }
        data = request("GET", f"{kind}?{urlencode(query)}")
        items += data[kind]
        page = data["meta"]["pagination"]["next_page"]
    return items


def _wait_until_gone(request: Request, selector: str, ids: set[int]) -> None:
    deadline = time.monotonic() + SERVER_GONE_TIMEOUT_S
    while ids & {server["id"] for server in list_resources(request, SERVERS, selector)}:
        if time.monotonic() > deadline:
            raise SystemExit(
                f"servers {sorted(ids)} still exist after {SERVER_GONE_TIMEOUT_S} s"
            )
        time.sleep(SERVER_GONE_POLL_S)


def _created(item: dict) -> datetime:
    return datetime.fromisoformat(item["created"])


def _expired(
    resources: dict[str, list[dict]], cutoff: datetime, keep: frozenset[str]
) -> dict[str, list[dict]]:
    newest_by_run: dict[str, datetime] = {}
    for item in (item for items in resources.values() for item in items):
        run, created = item["labels"].get(RUN_LABEL), _created(item)
        if run is not None:
            newest_by_run[run] = max(newest_by_run.get(run, created), created)

    def is_expired(item: dict) -> bool:
        run = item["labels"].get(RUN_LABEL)
        return run not in keep and newest_by_run.get(run, _created(item)) < cutoff

    return {
        kind: [item for item in items if is_expired(item)]
        for kind, items in resources.items()
    }


def sweep(
    request: Request,
    *,
    run: str | None,
    cutoff: datetime | None,
    dry_run: bool,
    keep: frozenset[str] = frozenset(),
    out: Callable[[str], object] = print,
) -> int:
    selector = (
        MANAGED_SELECTOR if run is None else f"{MANAGED_SELECTOR},{RUN_LABEL}={run}"
    )
    action = "would delete" if dry_run else "deleting"
    resources = {
        kind: list_resources(request, kind, selector) for kind in RESOURCE_KINDS
    }
    if cutoff is not None:
        resources = _expired(resources, cutoff, keep)
    count = 0
    for kind, items in resources.items():
        for item in items:
            out(f"{action} {kind} {item['id']} {item['name'] or item['description']}")
            if not dry_run:
                request("DELETE", f"{kind}/{item['id']}")
        if kind == SERVERS and items and not dry_run:
            _wait_until_gone(request, selector, {item["id"] for item in items})
        count += len(items)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete Hetzner Cloud resources labelled vigil-managed=true."
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--run", help="delete every resource labelled with this run")
    scope.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=f"delete resources older than this (default: {DEFAULT_MAX_AGE_HOURS})",
    )
    parser.add_argument(
        "--keep-run",
        action="append",
        default=[],
        help="never delete resources of this run when sweeping by age (repeatable)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="list the resources without deleting"
    )
    args = parser.parse_args()
    token = os.environ.get("HCLOUD_TOKEN")
    if not token:
        parser.error("HCLOUD_TOKEN is not set")
    cutoff = (
        None if args.run else datetime.now(UTC) - timedelta(hours=args.max_age_hours)
    )
    count = sweep(
        http_request(token),
        run=args.run,
        cutoff=cutoff,
        dry_run=args.dry_run,
        keep=frozenset(args.keep_run),
    )
    print(f"{count} resources {'matched' if args.dry_run else 'deleted'}")


if __name__ == "__main__":
    main()
