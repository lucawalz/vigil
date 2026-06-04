from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml
from orchestrator.agent import _write_run_record, build_run_id
from orchestrator.models import RunRecord

_ORCHESTRATOR_RUN_TIMEOUT_S = float(
    os.environ.get("ORCHESTRATOR_RUN_TIMEOUT_S", "1800")
)
_HARNESS_WAIT_BUFFER_S = 300
DEFAULT_TIMEOUT_S = int(_ORCHESTRATOR_RUN_TIMEOUT_S + _HARNESS_WAIT_BUFFER_S)
DEFAULT_ORCHESTRATOR_URL = "http://localhost:9099"
BASELINE_KUSTOMIZATIONS = ("cluster-apps", "cluster-infrastructure")
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_EXIT_CODE = 10
DEFAULT_CIRCUIT_BREAKER_STATE_PATH = "/tmp/vigil-circuit-breaker.json"
_TRUNC = 300

log = logging.getLogger(__name__)

_INJECT_ASSERT_TIMEOUT_S = 90
_INJECT_ASSERT_POLL_INTERVAL_S = 5


class InjectAssertionFailed(RuntimeError):
    """Raised when the cluster does not show the expected failure within the timeout."""


def _kubectl(
    args: list[str], kubeconfig: str | None = None
) -> subprocess.CompletedProcess[str]:
    cmd = ["kubectl"]
    if kubeconfig:
        cmd += ["--kubeconfig", kubeconfig]
    return subprocess.run(cmd + args, capture_output=True, text=True, check=False)


def _ssh(host: str, command: str) -> subprocess.CompletedProcess[str]:
    ssh_key = os.environ.get("SSH_KEY_PATH", os.path.expanduser("~/.ssh/id_ed25519"))
    return subprocess.run(
        [
            "ssh",
            "-i",
            ssh_key,
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            f"root@{host}",
            command,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def _discover_failing_pod(
    namespace: str, deployment: str, kubeconfig: str | None
) -> str | None:
    """Return the first non-Running pod name matching the deployment app label."""
    r = _kubectl(
        ["get", "pods", "-n", namespace, "-l", f"app={deployment}", "-o", "json"],
        kubeconfig,
    )
    if r.returncode != 0:
        return None
    try:
        items = json.loads(r.stdout).get("items", [])
    except json.JSONDecodeError:
        return None
    for pod in items:
        if pod.get("status", {}).get("phase", "") != "Running":
            return pod["metadata"]["name"]
    if items:
        return items[0]["metadata"]["name"]
    return None


def _symptom_observed(verify: dict, kubeconfig: str | None = None) -> bool:
    """Return True when the fault symptom declared in verify_broken is present."""
    symptom = verify.get("symptom", "")
    ns = verify.get("namespace", "default")

    if symptom == "pod_not_ready":
        deployment = verify["deployment"]
        r = _kubectl(
            ["get", "deployment", deployment, "-n", ns, "-o", "json"], kubeconfig
        )
        if r.returncode != 0:
            return False
        obj = json.loads(r.stdout)
        spec_replicas = obj.get("spec", {}).get("replicas", 1)
        avail = obj.get("status", {}).get("availableReplicas", spec_replicas)
        if avail < spec_replicas:
            return True
        for cond in obj.get("status", {}).get("conditions", []):
            if cond.get("type") == "ReplicaFailure" and cond.get("status") == "True":
                return True
        r2 = _kubectl(
            ["get", "pods", "-n", ns, "-l", f"app={deployment}", "-o", "json"],
            kubeconfig,
        )
        if r2.returncode != 0:
            return False
        for pod in json.loads(r2.stdout).get("items", []):
            phase = pod.get("status", {}).get("phase", "")
            if phase in ("Pending", "Failed", "Unknown"):
                return True
            for cs in pod.get("status", {}).get("containerStatuses", []):
                if not cs.get("ready", True):
                    return True
        return False

    if symptom == "replica_failure":
        deployment = verify["deployment"]
        r = _kubectl(
            ["get", "deployment", deployment, "-n", ns, "-o", "json"], kubeconfig
        )
        if r.returncode != 0:
            return False
        for cond in json.loads(r.stdout).get("status", {}).get("conditions", []):
            if cond.get("type") == "ReplicaFailure" and cond.get("status") == "True":
                return True
        return False

    if symptom == "deployment_unavailable":
        deployment = verify["deployment"]
        r = _kubectl(
            ["get", "deployment", deployment, "-n", ns, "-o", "json"], kubeconfig
        )
        if r.returncode != 0:
            return False
        obj = json.loads(r.stdout)
        spec_replicas = obj.get("spec", {}).get("replicas", 0)
        avail = obj.get("status", {}).get("availableReplicas", 0)
        return spec_replicas > 0 and avail == 0

    if symptom == "kustomization_suspended":
        name = verify["name"]
        kust_ns = verify.get("kustomization_namespace", "flux-system")
        r = _kubectl(
            ["get", "kustomization", name, "-n", kust_ns, "-o", "json"], kubeconfig
        )
        if r.returncode != 0:
            return False
        return json.loads(r.stdout).get("spec", {}).get("suspend", False) is True

    if symptom == "kustomization_not_ready":
        name = verify["name"]
        kust_ns = verify.get("kustomization_namespace", "flux-system")
        r = _kubectl(
            ["get", "kustomization", name, "-n", kust_ns, "-o", "json"], kubeconfig
        )
        if r.returncode != 0:
            return False
        for cond in json.loads(r.stdout).get("status", {}).get("conditions", []):
            if cond.get("type") == "Ready" and cond.get("status") == "False":
                return True
        return False

    if symptom == "node_not_ready":
        node = verify["node"]
        r = _kubectl(["get", "node", node, "-o", "json"], kubeconfig)
        if r.returncode != 0:
            return False
        for cond in json.loads(r.stdout).get("status", {}).get("conditions", []):
            if cond.get("type") == "Ready" and cond.get("status") != "True":
                return True
        return False

    if symptom == "node_disk_pressure":
        node = verify["node"]
        r = _kubectl(["get", "node", node, "-o", "json"], kubeconfig)
        if r.returncode != 0:
            return False
        for cond in json.loads(r.stdout).get("status", {}).get("conditions", []):
            if cond.get("type") == "DiskPressure" and cond.get("status") == "True":
                return True
        return False

    if symptom == "systemd_unit_inactive":
        host = verify["host"]
        unit = verify["unit"]
        r = _ssh(host, f"systemctl is-active {unit}")
        return r.returncode != 0

    if symptom == "sysctl_modified":
        host = verify["host"]
        key = verify["key"]
        expected = str(verify["expected_value"])
        r = _ssh(host, f"sysctl -n {key}")
        return r.returncode == 0 and r.stdout.strip() == expected

    log.warning("unknown symptom kind %r - skipping assertion", symptom)
    return True


def _wait_for_inject_symptom(
    scenario_id: str, verify: dict, scenarios_dir: Path
) -> None:
    """Poll until the declared failure symptom is observed or the timeout expires."""
    kubeconfig = os.environ.get("EVAL_RUNNER_KUBECONFIG") or None
    timeout = int(verify.get("timeout_s", _INJECT_ASSERT_TIMEOUT_S))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _symptom_observed(verify, kubeconfig):
            log.info(
                "inject-assert: symptom %r confirmed for %s",
                verify["symptom"],
                scenario_id,
            )
            return
        time.sleep(_INJECT_ASSERT_POLL_INTERVAL_S)
    raise InjectAssertionFailed(
        f"scenario {scenario_id}: symptom {verify['symptom']!r} not observed"
        f" within {timeout}s"
    )


def _emit_inject_failed_record(
    scenario_id: str,
    seed: int,
    model: str,
    reason: str,
    runs_dir: Path | None = None,
) -> Path:
    run_id, seed_str, sha7 = build_run_id(scenario_id, model, seed=seed)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = RunRecord(
        run_id=run_id,
        scenario=scenario_id,
        seed=seed_str,
        model=model,
        git_sha7=sha7,
        started_at=now,
        ended_at=now,
        outcome="inject_did_not_break",
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
        setup_error=reason,
        model_version=model,
    )
    _write_run_record(record)
    if runs_dir is None:
        runs_dir = Path(os.environ.get("EVAL_RUNS_DIR", "eval/runs"))
    return runs_dir / f"{run_id}.json"


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
    baseline["cluster_apps"] = _capture_kust_condition(BASELINE_KUSTOMIZATIONS[0])
    baseline["cluster_infra"] = _capture_kust_condition(BASELINE_KUSTOMIZATIONS[1])
    all_ready = (
        baseline["cluster_apps"]["ready"] == "True"
        and baseline["cluster_infra"]["ready"] == "True"
    )
    if not all_ready:
        log.warning(
            "cluster baseline not ready:"
            " cluster-apps=%s(reason=%s) cluster-infra=%s(reason=%s)",
            baseline["cluster_apps"]["ready"],
            baseline["cluster_apps"]["reason"],
            baseline["cluster_infra"]["ready"],
            baseline["cluster_infra"]["reason"],
        )
    return baseline, all_ready


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


_POD_SCOPED_ALERTS: frozenset[str] = frozenset(
    {"KubePodCrashLooping", "KubePodNotReady", "KubeContainerWaiting"}
)

_K8S_LABEL_KEYS: frozenset[str] = frozenset(
    {
        "deployment",
        "kustomization",
        "namespace",
        "pod",
        "statefulset",
        "daemonset",
        "name",
        "service",
    }
)

_SYSCTL_MODIFIED_SYMPTOM = "sysctl_modified"
_SYSCTL_KEY_LABEL = "sysctl_key"


def _load_scenario(scenario_id: str) -> dict[str, Any]:
    scenarios_dir = Path(os.environ.get("VIGIL_SCENARIOS_DIR", "eval/scenarios"))
    scenario_yaml = scenarios_dir / scenario_id / "scenario.yaml"
    if scenario_yaml.exists():
        with scenario_yaml.open() as f:
            return yaml.safe_load(f) or {}
    return {}


def _build_fault_event(
    scenario_id: str, target_host: str | None = None
) -> dict[str, Any]:
    kubeconfig = os.environ.get("EVAL_RUNNER_KUBECONFIG") or None
    scenario = _load_scenario(scenario_id)
    alert_name = scenario.get("alert_name") or scenario_id
    inject_params: dict[str, Any] = scenario.get("inject_params") or {}
    labels: dict[str, str] = {"alertname": alert_name}

    if alert_name in _POD_SCOPED_ALERTS:
        namespace = str(inject_params.get("namespace", "default"))
        deployment = str(inject_params.get("deployment", ""))
        labels["namespace"] = namespace
        if deployment:
            pod_name = _discover_failing_pod(namespace, deployment, kubeconfig)
            if pod_name:
                labels["pod"] = pod_name
            else:
                labels["deployment"] = deployment
    else:
        for key in _K8S_LABEL_KEYS:
            if key in inject_params:
                labels[key] = str(inject_params[key])

    verify_broken: dict[str, Any] = scenario.get("verify_broken") or {}
    if verify_broken.get("symptom") == _SYSCTL_MODIFIED_SYMPTOM:
        sysctl_key = verify_broken.get("key")
        if sysctl_key:
            labels[_SYSCTL_KEY_LABEL] = str(sysctl_key)

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
) -> Path:
    webhook_secret = os.environ.get("VIGIL_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise ValueError("VIGIL_WEBHOOK_SECRET is not set")
    fault_event = _build_fault_event(scenario_id, target_host=target_host)
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
    wait_flux_ready_sh = scenarios_dir.parent / "scripts" / "wait-flux-ready.sh"
    reset_sh = _script_path(scenarios_dir, scenario_id, "reset.sh")
    inject_sh = _script_path(scenarios_dir, scenario_id, "inject.sh")

    if reset_baseline_sh.is_file():
        log.info("resetting chore/eval-cluster-baseline before %s", scenario_id)
        _run_script(reset_baseline_sh, seed, verbose=verbose)

    if wait_flux_ready_sh.is_file():
        log.info("waiting for flux ready before %s", scenario_id)
        result = subprocess.run(
            [str(wait_flux_ready_sh)],
            capture_output=not verbose,
            text=True,
            check=False,
        )
        if verbose and result.stdout:
            log.debug("wait-flux-ready stdout:\n%s", result.stdout.rstrip())
        if result.returncode != 0:
            raise RuntimeError(
                f"wait-flux-ready.sh exited {result.returncode}: "
                + (result.stderr.strip() if result.stderr else "")
            )

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
    verify_broken: dict | None = None
    scenario_yaml = scenarios_dir / scenario_id / "scenario.yaml"
    if scenario_yaml.exists():
        with scenario_yaml.open() as f:
            data = yaml.safe_load(f)
        target_host = (data.get("inject_params") or {}).get("target_host")
        verify_broken = data.get("verify_broken") or None

    if verify_broken:
        try:
            _wait_for_inject_symptom(scenario_id, verify_broken, scenarios_dir)
        except InjectAssertionFailed as exc:
            log.error("inject-assert failed for %s: %s", scenario_id, exc)
            result_path = _emit_inject_failed_record(
                scenario_id, seed, model, str(exc), runs_dir
            )
            return result_path
    else:
        log.warning(
            "no verify_broken block for %s - skipping inject assertion", scenario_id
        )

    return await trigger_and_wait(
        scenario_id=scenario_id,
        seed=seed,
        orchestrator_url=orchestrator_url,
        runs_dir=runs_dir,
        model=model,
        timeout_s=timeout_s,
        verbose=verbose,
        target_host=target_host,
    )
