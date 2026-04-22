from __future__ import annotations

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx

DEFAULT_TIMEOUT_S = 600
DEFAULT_ORCHESTRATOR_URL = "http://localhost:9099"


def _script_path(scenarios_dir: Path, scenario_id: str, name: str) -> Path:
    return scenarios_dir / scenario_id / name


def _run_script(path: Path, seed: int) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"script not found: {path}")
    result = subprocess.run(
        [str(path), str(seed)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{path} exited {result.returncode}: {result.stderr.strip()}"
        )


def _build_fault_event(scenario_id: str) -> dict[str, Any]:
    return {
        "receiver": "vigil-webhook",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {"alertname": f"EvalHarness-{scenario_id}"},
                "annotations": {"summary": f"eval harness trigger for {scenario_id}"},
                "startsAt": "1970-01-01T00:00:00Z",
                "endsAt": "",
                "generatorURL": "",
                "fingerprint": f"eval-{scenario_id}",
            }
        ],
        "groupLabels": {"alertname": f"EvalHarness-{scenario_id}"},
        "commonLabels": {"alertname": f"EvalHarness-{scenario_id}"},
        "commonAnnotations": {},
        "externalURL": "",
        "version": "4",
        "groupKey": f"eval/{scenario_id}",
        "truncatedAlerts": 0,
    }


async def _healthz_check(client: httpx.AsyncClient, orchestrator_url: str) -> None:
    try:
        r = await client.get(f"{orchestrator_url}/healthz", timeout=5)
        r.raise_for_status()
    except httpx.ConnectError as e:
        raise RuntimeError(
            f"Orchestrator not reachable at {orchestrator_url} — start it first "
            f"(uv run uvicorn orchestrator.main:app --port 9099). Underlying: {e}"
        ) from e


async def trigger_and_wait(
    scenario_id: str,
    seed: int,
    orchestrator_url: str,
    runs_dir: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Path:
    webhook_secret = os.environ.get("VIGIL_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise ValueError("VIGIL_WEBHOOK_SECRET is not set")
    fault_event = _build_fault_event(scenario_id)
    async with httpx.AsyncClient() as client:
        await _healthz_check(client, orchestrator_url)
        resp = await client.post(
            f"{orchestrator_url}/webhook",
            params={"scenario": scenario_id, "seed": seed},
            json=fault_event,
            headers={"Authorization": f"Bearer {webhook_secret}"},
            timeout=30,
        )
        resp.raise_for_status()
        run_id = resp.json()["run_id"]

    result_path = runs_dir / f"{run_id}.json"
    result_path.unlink(missing_ok=True)
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    while loop.time() < deadline:
        if result_path.exists():
            return result_path
        await asyncio.sleep(2)
    raise TimeoutError(
        f"No result file for run_id={run_id} within {timeout_s}s at {result_path}"
    )


async def run_one(
    scenario_id: str,
    seed: int,
    scenarios_dir: Path,
    orchestrator_url: str = DEFAULT_ORCHESTRATOR_URL,
    runs_dir: Path | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> Path:
    if runs_dir is None:
        runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))

    reset_sh = _script_path(scenarios_dir, scenario_id, "reset.sh")
    inject_sh = _script_path(scenarios_dir, scenario_id, "inject.sh")

    _run_script(reset_sh, seed)
    _run_script(inject_sh, seed)

    return await trigger_and_wait(
        scenario_id=scenario_id,
        seed=seed,
        orchestrator_url=orchestrator_url,
        runs_dir=runs_dir,
        timeout_s=timeout_s,
    )
