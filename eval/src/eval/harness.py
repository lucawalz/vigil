from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from orchestrator.agent import _write_run_record, build_run_id
from orchestrator.models import RunRecord

DEFAULT_TIMEOUT_S = 600
DEFAULT_ORCHESTRATOR_URL = "http://localhost:9099"
BASELINE_RETRY_COUNT = 2
BASELINE_RETRY_SLEEP_S = 30
BASELINE_KUSTOMIZATIONS = ("cluster-apps", "cluster-infrastructure")
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_EXIT_CODE = 10
DEFAULT_CIRCUIT_BREAKER_STATE_PATH = "/tmp/vigil-circuit-breaker.json"
_TRUNC = 300

log = logging.getLogger(__name__)


def _script_path(scenarios_dir: Path, scenario_id: str, name: str) -> Path:
    return scenarios_dir / scenario_id / name


def _run_script(path: Path, seed: int, verbose: bool = False) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"script not found: {path}")
    result = subprocess.run(
        [str(path), str(seed)],
        capture_output=True,
        text=True,
        check=False,
    )
    if verbose:
        if result.stdout:
            log.debug("%s stdout:\n%s", path.name, result.stdout.rstrip())
        if result.stderr:
            log.debug("%s stderr:\n%s", path.name, result.stderr.rstrip())
    if result.returncode != 0:
        raise RuntimeError(
            f"{path} exited {result.returncode}: {result.stderr.strip()}"
        )


def _capture_kust_condition(name: str) -> dict:
    kubeconfig = os.environ.get("EVAL_RUNNER_KUBECONFIG", "")
    cmd = ["kubectl"]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]
    cmd += ["get", "kustomization", name, "-n", "flux-system", "-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {
            "ready": "Unknown",
            "reason": "kubectl_error",
            "message": result.stderr.strip()[:500],
        }
    try:
        obj = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {
            "ready": "Unknown",
            "reason": "kubectl_error",
            "message": str(result.stdout)[:500],
        }
    conditions = obj.get("status", {}).get("conditions", [])
    for cond in conditions:
        if cond.get("type") == "Ready":
            return {
                "ready": cond.get("status", "Unknown"),
                "reason": cond.get("reason", ""),
                "message": cond.get("message", ""),
            }
    return {"ready": "Unknown", "reason": "no_ready_condition", "message": ""}


async def capture_flux_baseline() -> tuple[dict, bool]:
    baseline: dict = {}
    for attempt in range(BASELINE_RETRY_COUNT + 1):
        baseline["cluster_apps"] = _capture_kust_condition(BASELINE_KUSTOMIZATIONS[0])
        baseline["cluster_infra"] = _capture_kust_condition(BASELINE_KUSTOMIZATIONS[1])
        all_ready = (
            baseline["cluster_apps"]["ready"] == "True"
            and baseline["cluster_infra"]["ready"] == "True"
        )
        if all_ready:
            return baseline, True
        log.warning(
            "cluster baseline not ready (attempt %d/%d):"
            " cluster-apps=%s(reason=%s) cluster-infra=%s(reason=%s)",
            attempt + 1,
            BASELINE_RETRY_COUNT + 1,
            baseline["cluster_apps"]["ready"],
            baseline["cluster_apps"]["reason"],
            baseline["cluster_infra"]["ready"],
            baseline["cluster_infra"]["reason"],
        )
        if attempt < BASELINE_RETRY_COUNT:
            await asyncio.sleep(BASELINE_RETRY_SLEEP_S)
    return baseline, False


def _emit_baseline_degraded_record(
    scenario_id: str,
    seed: int,
    model: str,
    baseline: dict,
    runs_dir: Path | None = None,
) -> Path:
    run_id, seed_str, sha7 = build_run_id(scenario_id, model, seed=seed)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if baseline["cluster_infra"]["ready"] != "True":
        sub_reason = "cluster_infrastructure_not_ready"
    elif baseline["cluster_apps"]["ready"] != "True":
        sub_reason = "cluster_apps_not_ready"
    else:
        sub_reason = "unknown"
    record = RunRecord(
        run_id=run_id,
        scenario=scenario_id,
        seed=seed_str,
        model=model,
        git_sha7=sha7,
        started_at=now,
        ended_at=now,
        outcome="baseline_degraded",
        success_rate=False,
        diagnosis_accuracy=None,
        MTTR_s=None,
        destructive_repair=False,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tool_calls=0,
        iteration_count=0,
        autonomy_level="full",
        actions_taken=[],
        setup_error=sub_reason,
        model_version=model,
    )
    _write_run_record(record)
    if runs_dir is None:
        runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))
    return runs_dir / f"{run_id}.json"


def _load_circuit_breaker_count() -> int:
    state_path = os.environ.get(
        "VIGIL_CIRCUIT_BREAKER_STATE", DEFAULT_CIRCUIT_BREAKER_STATE_PATH
    )
    try:
        with open(state_path) as f:
            loaded = json.load(f)
        return int(loaded.get("consecutive_baseline_degraded", 0))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return 0


def _record_circuit_breaker_baseline_degraded() -> int:
    state_path = os.environ.get(
        "VIGIL_CIRCUIT_BREAKER_STATE", DEFAULT_CIRCUIT_BREAKER_STATE_PATH
    )
    new_count = _load_circuit_breaker_count() + 1
    try:
        with open(state_path, "w") as f:
            json.dump({"consecutive_baseline_degraded": new_count}, f)
    except OSError:
        pass
    return new_count


def _reset_circuit_breaker() -> None:
    state_path = os.environ.get(
        "VIGIL_CIRCUIT_BREAKER_STATE", DEFAULT_CIRCUIT_BREAKER_STATE_PATH
    )
    try:
        with open(state_path, "w") as f:
            json.dump({"consecutive_baseline_degraded": 0}, f)
    except OSError:
        pass


def _load_scenario_alert_name(scenario_id: str) -> str:
    scenarios_dir = Path(os.environ.get("VIGIL_SCENARIOS_DIR", "eval/scenarios"))
    scenario_yaml = scenarios_dir / scenario_id / "scenario.yaml"
    if scenario_yaml.exists():
        with scenario_yaml.open() as f:
            data = yaml.safe_load(f) or {}
        name = data.get("alert_name", "")
        if name:
            return name
    return scenario_id


def _build_fault_event(
    scenario_id: str, target_host: str | None = None
) -> dict[str, Any]:
    alert_name = _load_scenario_alert_name(scenario_id)
    labels: dict[str, str] = {"alertname": alert_name}
    if target_host:
        labels["node"] = target_host
    return {
        "receiver": "vigil-webhook",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": labels,
                "annotations": {"summary": f"eval harness trigger for {scenario_id}"},
                "startsAt": "1970-01-01T00:00:00Z",
                "endsAt": "",
                "generatorURL": "",
                "fingerprint": f"eval-{scenario_id}",
            }
        ],
        "groupLabels": {"alertname": alert_name},
        "commonLabels": labels,
        "commonAnnotations": {},
        "externalURL": "",
        "version": "4",
        "groupKey": f"eval/{alert_name}",
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


def _emit_trace_line(line: str) -> None:
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        return
    phase = entry.get("phase", "?")
    for part in entry.get("parts", []):
        kind = part.get("part_kind") or part.get("type", "")
        if kind == "tool-call":
            args = part.get("args", {})
            if isinstance(args, dict) and "args_dict" in args:
                args = args["args_dict"]
            args_s = json.dumps(args) if isinstance(args, dict) else str(args)
            if len(args_s) > _TRUNC:
                args_s = args_s[:_TRUNC] + "…"
            log.info("[%s] → %s(%s)", phase, part.get("tool_name", "?"), args_s)
        elif kind == "tool-return":
            content = str(part.get("content", ""))
            if len(content) > _TRUNC:
                content = content[:_TRUNC] + "…"
            log.debug("[%s] ← %s: %s", phase, part.get("tool_name", "?"), content)
        elif kind == "text":
            content = part.get("content", "").strip()
            if content:
                if len(content) > _TRUNC:
                    content = content[:_TRUNC] + "…"
                log.debug("[%s] model: %s", phase, content)


async def _tail_trace(trace_path: Path, stop: asyncio.Event) -> None:
    while not trace_path.exists():
        if stop.is_set():
            return
        await asyncio.sleep(0.5)
    offset = 0
    while True:
        with trace_path.open() as f:
            f.seek(offset)
            for raw in f:
                raw = raw.strip()
                if raw:
                    _emit_trace_line(raw)
            offset = f.tell()
        if stop.is_set():
            return
        await asyncio.sleep(0.5)


async def trigger_and_wait(
    scenario_id: str,
    seed: int,
    orchestrator_url: str,
    runs_dir: Path,
    model: str,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    verbose: bool = False,
    target_host: str | None = None,
    flux_baseline: dict | None = None,
) -> Path:
    webhook_secret = os.environ.get("VIGIL_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise ValueError("VIGIL_WEBHOOK_SECRET is not set")
    if flux_baseline is None:
        flux_baseline, _ = await capture_flux_baseline()
    fault_event = _build_fault_event(scenario_id, target_host=target_host)
    fault_event["flux_baseline"] = flux_baseline
    async with httpx.AsyncClient() as client:
        await _healthz_check(client, orchestrator_url)
        log.info("triggering orchestrator webhook for %s", scenario_id)
        resp = await client.post(
            f"{orchestrator_url}/webhook",
            params={"scenario": scenario_id, "seed": seed, "model": model},
            json=fault_event,
            headers={"Authorization": f"Bearer {webhook_secret}"},
            timeout=720,
        )
        resp.raise_for_status()
        run_id = resp.json()["run_id"]

    log.info("run_id=%s — polling for result", run_id)
    result_path = runs_dir / f"{run_id}.json"
    result_path.unlink(missing_ok=True)

    stop = asyncio.Event()
    tail: asyncio.Task[None] | None = None
    if verbose:
        tail = asyncio.create_task(
            _tail_trace(runs_dir / f"{run_id}_trace.jsonl", stop)
        )

    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout_s
    last_log = loop.time()
    try:
        while loop.time() < deadline:
            if result_path.exists():
                return result_path
            await asyncio.sleep(2)
            now = loop.time()
            if now - last_log >= 30:
                log.debug(
                    "still waiting for %s ... %.0fs elapsed",
                    run_id,
                    now - (deadline - timeout_s),
                )
                last_log = now
        raise TimeoutError(
            f"No result file for run_id={run_id} within {timeout_s}s at {result_path}"
        )
    finally:
        stop.set()
        if tail is not None:
            await tail


async def run_one(
    scenario_id: str,
    seed: int,
    scenarios_dir: Path,
    model: str,
    orchestrator_url: str = DEFAULT_ORCHESTRATOR_URL,
    runs_dir: Path | None = None,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    verbose: bool = False,
) -> Path:
    if runs_dir is None:
        runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))

    reset_baseline_sh = scenarios_dir.parent / "scripts" / "reset-eval-baseline.sh"
    reset_sh = _script_path(scenarios_dir, scenario_id, "reset.sh")
    inject_sh = _script_path(scenarios_dir, scenario_id, "inject.sh")

    if reset_baseline_sh.is_file():
        log.info("resetting chore/eval-cluster-baseline before %s", scenario_id)
        _run_script(reset_baseline_sh, seed, verbose=verbose)

    log.info("running reset.sh for %s", scenario_id)
    _run_script(reset_sh, seed, verbose=verbose)

    baseline, all_ready = await capture_flux_baseline()
    if not all_ready:
        result_path = _emit_baseline_degraded_record(
            scenario_id, seed, model, baseline, runs_dir
        )
        new_count = _record_circuit_breaker_baseline_degraded()
        log.error(
            "campaign baseline_degraded count=%d/%d (scenario=%s)",
            new_count,
            CIRCUIT_BREAKER_THRESHOLD,
            scenario_id,
        )
        if new_count >= CIRCUIT_BREAKER_THRESHOLD:
            log.error(
                "Campaign aborted: %d consecutive baseline_degraded"
                " — check cluster-infrastructure readiness before retrying",
                new_count,
            )
            sys.exit(CIRCUIT_BREAKER_EXIT_CODE)
        return result_path

    _reset_circuit_breaker()
    log.info("running inject.sh for %s", scenario_id)
    _run_script(inject_sh, seed, verbose=verbose)

    target_host: str | None = None
    scenario_yaml = scenarios_dir / scenario_id / "scenario.yaml"
    if scenario_yaml.exists():
        with scenario_yaml.open() as f:
            data = yaml.safe_load(f)
        target_host = (data.get("inject_params") or {}).get("target_host")

    return await trigger_and_wait(
        scenario_id=scenario_id,
        seed=seed,
        orchestrator_url=orchestrator_url,
        runs_dir=runs_dir,
        model=model,
        timeout_s=timeout_s,
        verbose=verbose,
        target_host=target_host,
        flux_baseline=baseline,
    )
