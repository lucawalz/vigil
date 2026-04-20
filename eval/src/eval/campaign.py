from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Iterator


def completed_run_ids(runs_index_path: Path) -> set[str]:
    if not runs_index_path.exists():
        return set()
    ids: set[str] = set()
    with runs_index_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            ids.add(json.loads(line)["run_id"])
    return ids


def combinations(
    scenarios: list[str],
    seeds: list[int],
    models: list[str],
) -> Iterator[tuple[str, int, str]]:
    for scenario, seed, model in itertools.product(scenarios, seeds, models):
        yield (scenario, seed, model)
