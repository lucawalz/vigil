"""Tests for the eval harness: reset->inject->POST->poll flow."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import eval.harness as harness_mod
import httpx
import pytest
from common.constants import SHUTDOWN_DRAIN_S
from eval.harness import DEFAULT_EVAL_BRANCH, eval_branch, run_one, trigger_and_wait
from orchestrator.agent import MAX_TRIES, retry_run_id
from orchestrator.models import RunRecord


@pytest.mark.parametrize(
    ("environ", "expected"),
    [
        ({"VIGIL_EVAL_BRANCH": "eval/123/k8s-1"}, "eval/123/k8s-1"),
        ({"VIGIL_EVAL_BRANCH": ""}, DEFAULT_EVAL_BRANCH),
        ({}, DEFAULT_EVAL_BRANCH),
    ],
)
def test_eval_branch_falls_back_like_the_reset_script(
    environ: dict[str, str], expected: str
) -> None:
    assert eval_branch(environ) == expected


def _make_run_record(run_id: str = "k8s-3_1_test-model_abc1234") -> dict:
    return {
        "run_id": run_id,
        "scenario": "k8s-3",
        "seed": "1",
        "model": "test-model",
        "git_sha7": "abc1234",
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:01:00Z",
        "outcome": "success",
        "success_rate": True,
        "diagnosis_accuracy": None,
        "MTTR_s": 60.0,
        "destructive_repair": False,
        "rollback_triggered": False,
        "rollback_success": None,
        "total_input_tokens": 100,
        "total_output_tokens": 50,
        "total_tool_calls": 3,
        "iteration_count": 3,
        "autonomy_level": "full",
    }


def _fake_script(path: Path, seed: int) -> None:
    pass


def _make_fake_subprocess_run(returncode: int = 0):
    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = returncode
        result.stderr = ""
        return result

    return fake_run


async def test_reset_runs_before_inject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_order: list[str] = []
    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "k8s-3"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "reset.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "inject.sh").write_text("#!/bin/bash\nexit 0")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    def fake_run(cmd, **kwargs):
        if "reset.sh" in cmd[0]:
            call_order.append("reset")
        elif "inject.sh" in cmd[0]:
            call_order.append("inject")
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)

    run_id = "k8s-3_1_test-model_abc1234"

    async def fake_trigger(*args, **kwargs) -> Path:
        result_file = tmp_path / "runs" / f"{run_id}.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        import json

        result_file.write_text(json.dumps(_make_run_record(run_id)))
        return result_file

    monkeypatch.setattr(harness_mod, "trigger_and_wait", fake_trigger)

    await run_one(
        scenario_id="k8s-3",
        seed=1,
        scenarios_dir=scenarios_dir,
        model="test-model",
        runs_dir=tmp_path / "runs",
        timeout_s=5,
    )

    assert call_order == ["reset", "inject"], (
        f"Expected reset before inject, got: {call_order}"
    )


async def test_inject_subprocess_failure_aborts_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "k8s-3"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "reset.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "inject.sh").write_text("#!/bin/bash\nexit 0")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        if "inject.sh" in cmd[0]:
            result.returncode = 1
            result.stderr = "inject failed"
        else:
            result.returncode = 0
            result.stderr = ""
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)
    post_called = False

    async def fake_trigger(*args, **kwargs) -> Path:
        nonlocal post_called
        post_called = True
        return tmp_path / "dummy.json"

    monkeypatch.setattr(harness_mod, "trigger_and_wait", fake_trigger)

    with pytest.raises(RuntimeError):
        await run_one(
            scenario_id="k8s-3",
            seed=1,
            scenarios_dir=scenarios_dir,
            model="test-model",
            runs_dir=tmp_path / "runs",
            timeout_s=5,
        )

    assert not post_called, "POST should not be called when inject.sh fails"


async def test_post_includes_scenario_and_seed_query_params(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "test-secret")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    captured: dict = {}
    run_id = "k8s-3_1_test-model_abc1234"
    result_file = tmp_path / f"{run_id}.json"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def post(self, url, **kwargs):
            captured.update(kwargs)
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value={"run_id": run_id, "outcome": "success"})
            return resp

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)

    async def fake_sleep(t):
        result_file.write_text("{}")

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    await trigger_and_wait(
        scenario_id="k8s-3",
        seed=1,
        orchestrator_url="http://localhost:9099",
        runs_dir=tmp_path,
        model="test-model",
        timeout_s=5,
    )

    expected = {"scenario": "k8s-3", "seed": 1, "model": "test-model"}
    assert captured.get("params") == expected


async def test_post_includes_bearer_auth_header(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "super-secret")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    captured_headers: dict = {}
    run_id = "k8s-3_1_test-model_abc1234"
    result_file = tmp_path / f"{run_id}.json"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def post(self, url, **kwargs):
            captured_headers.update(kwargs.get("headers", {}))
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value={"run_id": run_id, "outcome": "success"})
            return resp

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)

    async def fake_sleep(t):
        result_file.write_text("{}")

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    await trigger_and_wait(
        scenario_id="k8s-3",
        seed=1,
        orchestrator_url="http://localhost:9099",
        runs_dir=tmp_path,
        model="test-model",
        timeout_s=5,
    )

    assert captured_headers.get("Authorization") == "Bearer super-secret"


async def test_uses_response_run_id_for_polling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "s")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    server_run_id = "k8s-3_1_test-model_server_computed"
    result_file = tmp_path / f"{server_run_id}.json"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def post(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(
                return_value={"run_id": server_run_id, "outcome": "success"}
            )
            return resp

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)

    poll_count = 0

    async def fake_sleep(t):
        nonlocal poll_count
        poll_count += 1
        if poll_count == 1:
            result_file.write_text("{}")

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    result = await trigger_and_wait(
        scenario_id="k8s-3",
        seed=1,
        orchestrator_url="http://localhost:9099",
        runs_dir=tmp_path,
        model="test-model",
        timeout_s=5,
    )

    assert result == result_file


async def test_timeout_when_result_file_never_appears(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "s")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def post(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(
                return_value={"run_id": "k8s-3_1_m_abc", "outcome": "success"}
            )
            return resp

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)

    call_count = 0

    async def fake_sleep(t):
        nonlocal call_count
        call_count += 1
        if call_count > 5:
            raise asyncio.CancelledError

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    loop_time_values = iter([0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])

    class FakeLoop:
        def time(self):
            try:
                return next(loop_time_values)
            except StopIteration:
                return 100.0

    monkeypatch.setattr(harness_mod.asyncio, "get_event_loop", lambda: FakeLoop())

    with pytest.raises(TimeoutError):
        await trigger_and_wait(
            scenario_id="k8s-3",
            seed=1,
            orchestrator_url="http://localhost:9099",
            runs_dir=tmp_path,
            model="test-model",
            timeout_s=2,
        )


async def test_result_file_detected_when_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "s")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    run_id = "k8s-3_1_test_abc1234"
    result_file = tmp_path / f"{run_id}.json"

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            return resp

        async def post(self, url, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json = MagicMock(return_value={"run_id": run_id, "outcome": "success"})
            return resp

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)

    async def fake_sleep(t):
        result_file.write_text("{}")

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    result = await trigger_and_wait(
        scenario_id="k8s-3",
        seed=1,
        orchestrator_url="http://localhost:9099",
        runs_dir=tmp_path,
        model="test-model",
        timeout_s=10,
    )
    assert result == result_file


async def test_healthz_precheck_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "s")

    _ready_cond = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_capture_baseline():
        return {"cluster_apps": _ready_cond, "cluster_infra": _ready_cond}, True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_capture_baseline)

    class FakeClientConnectError:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClientConnectError)

    with pytest.raises(RuntimeError, match="Orchestrator not reachable"):
        await trigger_and_wait(
            scenario_id="k8s-3",
            seed=1,
            orchestrator_url="http://localhost:9099",
            runs_dir=tmp_path,
            model="test-model",
            timeout_s=5,
        )


def test_result_file_contains_all_eval_07_metric_fields() -> None:
    required = {
        "run_id",
        "scenario",
        "seed",
        "model",
        "git_sha7",
        "started_at",
        "ended_at",
        "outcome",
        "success_rate",
        "diagnosis_accuracy",
        "MTTR_s",
        "destructive_repair",
        "rollback_triggered",
        "rollback_success",
        "total_input_tokens",
        "total_output_tokens",
        "total_tool_calls",
        "iteration_count",
        "autonomy_level",
    }
    present = set(RunRecord.model_fields.keys())
    assert required.issubset(present), f"Missing fields: {required - present}"


_KUBECONFIG_NOT_READY_JSON = """{
  "status": {
    "conditions": [
      {"type": "Ready", "status": "False", "reason": "DependencyNotReady",
       "message": ""}
    ]
  }
}"""

_KUBECONFIG_READY_JSON = """{
  "status": {
    "conditions": [
      {"type": "Ready", "status": "True", "reason": "ReconciliationSucceeded",
       "message": ""}
    ]
  }
}"""

CIRCUIT_BREAKER_THRESHOLD = 3


async def test_baseline_capture_runs_between_reset_and_inject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    call_order: list[str] = []
    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "k8s-3"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "reset.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "inject.sh").write_text("#!/bin/bash\nexit 0")

    monkeypatch.setenv("EVAL_RUNNER_KUBECONFIG", "/fake/kubeconfig")

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        if "reset.sh" in cmd[0]:
            call_order.append("reset")
            result.stdout = ""
        elif "inject.sh" in cmd[0]:
            call_order.append("inject")
            result.stdout = ""
        elif "kubectl" in cmd[0] and "get" in cmd and "kustomization" in cmd:
            call_order.append("baseline")
            result.stdout = _KUBECONFIG_READY_JSON
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)

    run_id = "k8s-3_1_test-model_abc1234"

    async def fake_trigger(*args, **kwargs) -> Path:
        result_file = tmp_path / "runs" / f"{run_id}.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        import json as _json

        result_file.write_text(_json.dumps(_make_run_record(run_id)))
        return result_file

    monkeypatch.setattr(harness_mod, "trigger_and_wait", fake_trigger)

    await run_one(
        scenario_id="k8s-3",
        seed=1,
        scenarios_dir=scenarios_dir,
        model="test-model",
        runs_dir=tmp_path / "runs",
        timeout_s=5,
    )

    assert call_order == ["reset", "baseline", "baseline", "inject"], (
        f"Expected baseline capture between reset and inject, got: {call_order}"
    )


async def test_baseline_degraded_record_written_when_retries_exhausted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "k8s-3"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "reset.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "inject.sh").write_text("#!/bin/bash\nexit 0")
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    monkeypatch.setenv("EVAL_RUNNER_KUBECONFIG", "/fake/kubeconfig")
    monkeypatch.setenv("EVAL_RUNS_DIR", str(runs_dir))

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        if "reset.sh" in cmd[0]:
            pass
        elif "kubectl" in cmd[0]:
            result.stdout = _KUBECONFIG_NOT_READY_JSON
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)

    async def fake_sleep(_t):
        pass

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    trigger_called = False

    async def fake_trigger(*args, **kwargs) -> Path:
        nonlocal trigger_called
        trigger_called = True
        return tmp_path / "dummy.json"

    monkeypatch.setattr(harness_mod, "trigger_and_wait", fake_trigger)

    await run_one(
        scenario_id="k8s-3",
        seed=1,
        scenarios_dir=scenarios_dir,
        model="test-model",
        runs_dir=runs_dir,
        timeout_s=5,
    )

    assert not trigger_called, (
        "trigger_and_wait must not be called on degraded baseline"
    )
    import json as _json

    written_files = list(runs_dir.glob("*.json"))
    assert len(written_files) == 1, (
        f"Expected one run record written; found: {written_files}"
    )
    record_data = _json.loads(written_files[0].read_text())
    assert record_data["outcome"] == "baseline_degraded"
    assert record_data.get("setup_error"), "setup_error must be a non-empty string"


async def test_circuit_breaker_exits_with_code_10_after_three_consecutive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "k8s-3"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "reset.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "inject.sh").write_text("#!/bin/bash\nexit 0")
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    cb_state_file = tmp_path / "cb_state.json"
    monkeypatch.setenv("VIGIL_CIRCUIT_BREAKER_STATE", str(cb_state_file))
    monkeypatch.setenv("EVAL_RUNNER_KUBECONFIG", "/fake/kubeconfig")
    monkeypatch.setenv("EVAL_RUNS_DIR", str(runs_dir))

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        if "kubectl" in cmd[0]:
            result.stdout = _KUBECONFIG_NOT_READY_JSON
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)

    async def fake_sleep(_t):
        pass

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    run_id = "k8s-3_1_test-model_abc1234"

    async def fake_trigger(*args, **kwargs) -> Path:
        result_file = runs_dir / f"{run_id}.json"
        import json as _json

        result_file.write_text(_json.dumps(_make_run_record(run_id)))
        return result_file

    monkeypatch.setattr(harness_mod, "trigger_and_wait", fake_trigger)

    for _ in range(CIRCUIT_BREAKER_THRESHOLD - 1):
        await run_one(
            scenario_id="k8s-3",
            seed=1,
            scenarios_dir=scenarios_dir,
            model="test-model",
            runs_dir=runs_dir,
            timeout_s=5,
        )

    with pytest.raises(SystemExit) as exc_info:
        await run_one(
            scenario_id="k8s-3",
            seed=1,
            scenarios_dir=scenarios_dir,
            model="test-model",
            runs_dir=runs_dir,
            timeout_s=5,
        )

    assert exc_info.value.code == 10


def _write_k8s1_scenario(
    scenarios_dir: Path, alert_name: str = "KubeDeploymentReplicasMismatch"
) -> None:
    scenario_dir = scenarios_dir / "k8s-1"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml

    (scenario_dir / "scenario.yaml").write_text(
        _yaml.dump(
            {
                "id": "k8s-1",
                "name": "wrong-image-tag",
                "layer": "k8s",
                "root_cause_component": "Deployment/vigil-app",
                "expected_action": "flux_reconcile",
                "expected_resolution_path": "diagnosis -> flux_reconcile",
                "alert_name": alert_name,
            }
        )
    )


def test_build_fault_event_uses_alert_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.harness import _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    expected_alert_name = "KubeDeploymentReplicasMismatch"
    _write_k8s1_scenario(scenarios_dir, alert_name=expected_alert_name)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("k8s-1")

    assert payload["alerts"][0]["labels"]["alertname"] == expected_alert_name
    assert payload["groupLabels"]["alertname"] == expected_alert_name
    assert expected_alert_name in payload["groupKey"]


def test_no_scenario_id_leak(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eval.harness import _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    _write_k8s1_scenario(scenarios_dir)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("k8s-1")

    assert "k8s-1" not in payload["alerts"][0]["labels"]["alertname"]
    assert "k8s-1" not in payload["groupLabels"]["alertname"]
    assert "k8s-1" not in payload["groupKey"]


def test_no_evalharness_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from eval.harness import _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    _write_k8s1_scenario(scenarios_dir)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("k8s-1")

    assert "EvalHarness-" not in payload["alerts"][0]["labels"]["alertname"]
    assert "EvalHarness-" not in payload["groupLabels"]["alertname"]
    assert "EvalHarness-" not in payload["groupKey"]


def _agent_visible_alert_strings(payload: dict) -> list[str]:
    alert = payload["alerts"][0]
    return [
        alert["annotations"]["summary"],
        alert["fingerprint"],
        payload["groupKey"],
    ]


def test_alert_summary_fingerprint_groupkey_hide_scenario_and_eval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.harness import _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    _write_k8s1_scenario(scenarios_dir)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("k8s-1")

    for value in _agent_visible_alert_strings(payload):
        assert "k8s-1" not in value
        assert "eval" not in value.lower()
        assert "harness" not in value.lower()


def test_alert_fingerprint_is_deterministic_hex_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.harness import _FINGERPRINT_LEN, _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    _write_k8s1_scenario(scenarios_dir)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    fingerprint = _build_fault_event("k8s-1")["alerts"][0]["fingerprint"]

    assert len(fingerprint) == _FINGERPRINT_LEN
    assert all(c in "0123456789abcdef" for c in fingerprint)
    assert fingerprint == _build_fault_event("k8s-1")["alerts"][0]["fingerprint"]


def test_alert_name_falls_back_to_generic_constant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.harness import _DEFAULT_ALERT_NAME, _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "deceptive-2"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml

    (scenario_dir / "scenario.yaml").write_text(_yaml.dump({"id": "deceptive-2"}))
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("deceptive-2")

    assert payload["alerts"][0]["labels"]["alertname"] == _DEFAULT_ALERT_NAME
    assert "deceptive-2" not in payload["groupKey"]
    assert "deceptive-2" not in payload["alerts"][0]["annotations"]["summary"]


_SYSCTL_KEY = "net.bridge.bridge-nf-call-iptables"


def _write_sysctl_scenario(scenarios_dir: Path, key: str = _SYSCTL_KEY) -> None:
    scenario_dir = scenarios_dir / "os-drift-sysctl"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    import yaml as _yaml

    (scenario_dir / "scenario.yaml").write_text(
        _yaml.dump(
            {
                "id": "os-drift-sysctl",
                "name": "bridge-nf-call-iptables-disabled-at-runtime",
                "layer": "os",
                "expected_action": "nixos_rebuild",
                "alert_name": "KubePodNotReady",
                "verify_broken": {
                    "symptom": "sysctl_modified",
                    "host": "vigil-worker-1",
                    "key": key,
                    "expected_value": "0",
                    "timeout_s": 30,
                },
            }
        )
    )


def test_build_fault_event_never_injects_sysctl_key_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.harness import _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    _write_sysctl_scenario(scenarios_dir)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("os-drift-sysctl")

    assert "sysctl_key" not in payload["alerts"][0]["labels"]
    assert "sysctl_key" not in payload["commonLabels"]


def test_build_fault_event_omits_sysctl_key_for_non_sysctl_scenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from eval.harness import _build_fault_event

    scenarios_dir = tmp_path / "scenarios"
    _write_k8s1_scenario(scenarios_dir)
    monkeypatch.setenv("VIGIL_SCENARIOS_DIR", str(scenarios_dir))

    payload = _build_fault_event("k8s-1")

    assert "sysctl_key" not in payload["alerts"][0]["labels"]
    assert "sysctl_key" not in payload["commonLabels"]


_OLD_HEAD = "a" * 40
_NEW_HEAD = "b1c2d3e4" + "f" * 32
_FLUX_BRANCH = "eval/lab"
_KUST_GET = ["get", "kustomization", "cluster-apps", "-n", "flux-system"]


def _kust_json(revision: str | None = None, suspend: bool = False) -> str:
    import json as _json

    status = {"lastAttemptedRevision": revision} if revision else {}
    return _json.dumps({"spec": {"suspend": suspend}, "status": status})


def _fake_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    now = [0.0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(
        harness_mod,
        "time",
        SimpleNamespace(monotonic=lambda: now[0], sleep=sleep),
    )


def _uptake_runner(
    monkeypatch: pytest.MonkeyPatch,
    heads: list[str],
    kust_outputs: list[str],
    events: list[str],
) -> None:
    head_iter = iter(heads)

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""
        if cmd[0] == "git" and cmd[-2:] == ["rev-parse", "HEAD"]:
            result.stdout = next(head_iter) + "\n"
        elif cmd[0] == "git":
            result.stdout = _NEW_HEAD[:7] + "\n"
        elif cmd[0] == "kubectl" and cmd[-len(_KUST_GET) - 2 : -2] == _KUST_GET:
            events.append("kustomization")
            result.stdout = (
                kust_outputs.pop(0) if len(kust_outputs) > 1 else kust_outputs[0]
            )
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)


def _uptake_scenario(tmp_path: Path) -> Path:
    import yaml as _yaml

    scenarios_dir = tmp_path / "scenarios"
    scenario_dir = scenarios_dir / "k8s-3"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "reset.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "inject.sh").write_text("#!/bin/bash\nexit 0")
    (scenario_dir / "scenario.yaml").write_text(
        _yaml.dump({"verify_broken": {"symptom": "pod_crashloop"}})
    )
    return scenarios_dir


def _stub_run_one_collaborators(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, events: list[str]
) -> None:
    ready = {"ready": "True", "reason": "ReconciliationSucceeded", "message": ""}

    async def fake_baseline():
        return {"cluster_apps": ready, "cluster_infra": ready}, True

    async def fake_trigger(*args, **kwargs) -> Path:
        return tmp_path / "dummy.json"

    def fake_symptom(verify, kubeconfig=None):
        events.append("symptom")
        return True

    monkeypatch.setattr(harness_mod, "capture_flux_baseline", fake_baseline)
    monkeypatch.setattr(harness_mod, "trigger_and_wait", fake_trigger)
    monkeypatch.setattr(harness_mod, "_symptom_observed", fake_symptom)
    monkeypatch.setenv("VIGIL_REPO_ROOT", str(tmp_path))
    _fake_clock(monkeypatch)


async def test_symptom_window_opens_after_flux_takes_up_moved_head(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    _stub_run_one_collaborators(monkeypatch, tmp_path, events)
    _uptake_runner(
        monkeypatch,
        [_OLD_HEAD, _NEW_HEAD],
        [
            _kust_json(f"{_FLUX_BRANCH}@sha1:{_OLD_HEAD}"),
            _kust_json(f"{_FLUX_BRANCH}@sha1:{_NEW_HEAD}"),
        ],
        events,
    )

    await run_one(
        scenario_id="k8s-3",
        seed=1,
        scenarios_dir=_uptake_scenario(tmp_path),
        model="test-model",
        runs_dir=tmp_path / "runs",
        timeout_s=5,
    )

    assert events == ["kustomization", "kustomization", "symptom"]


async def test_unchanged_head_skips_flux_uptake_wait(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    _stub_run_one_collaborators(monkeypatch, tmp_path, events)
    _uptake_runner(monkeypatch, [_OLD_HEAD, _OLD_HEAD], [_kust_json()], events)

    await run_one(
        scenario_id="k8s-3",
        seed=1,
        scenarios_dir=_uptake_scenario(tmp_path),
        model="test-model",
        runs_dir=tmp_path / "runs",
        timeout_s=5,
    )

    assert events == ["symptom"]


async def test_flux_uptake_timeout_emits_inject_failed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json as _json

    events: list[str] = []
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    monkeypatch.setenv("EVAL_RUNS_DIR", str(runs_dir))
    _stub_run_one_collaborators(monkeypatch, tmp_path, events)
    _uptake_runner(
        monkeypatch,
        [_OLD_HEAD, _NEW_HEAD],
        [_kust_json(f"{_FLUX_BRANCH}@sha1:{_OLD_HEAD}")],
        events,
    )

    await run_one(
        scenario_id="k8s-3",
        seed=1,
        scenarios_dir=_uptake_scenario(tmp_path),
        model="test-model",
        runs_dir=runs_dir,
        timeout_s=5,
    )

    assert "symptom" not in events
    record = _json.loads(next(runs_dir.glob("*.json")).read_text())
    assert record["outcome"] == "inject_did_not_break"
    assert _NEW_HEAD in record["setup_error"]


def test_wait_for_flux_uptake_returns_when_kustomization_suspended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    _fake_clock(monkeypatch)
    _uptake_runner(monkeypatch, [], [_kust_json(suspend=True)], events)

    harness_mod._wait_for_flux_uptake("k8s-3", _NEW_HEAD)

    assert events == ["kustomization"]


def test_wait_for_flux_uptake_keeps_polling_through_kubectl_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_clock(monkeypatch)
    outputs = [
        (1, ""),
        (0, "not json"),
        (0, _kust_json(f"{_FLUX_BRANCH}@sha1:{_NEW_HEAD}")),
    ]

    def fake_run(cmd, **kwargs):
        result = MagicMock()
        result.stderr = ""
        result.returncode, result.stdout = (
            outputs.pop(0) if len(outputs) > 1 else outputs[0]
        )
        return result

    monkeypatch.setattr(harness_mod.subprocess, "run", fake_run)

    harness_mod._wait_for_flux_uptake("k8s-3", _NEW_HEAD)


def test_repo_head_is_none_without_repo_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIGIL_REPO_ROOT", raising=False)

    assert harness_mod._repo_head() is None


_INCIDENT_RUN_ID = "k8s-rollback-1_1_test-model_abc1234"
_AGENT_RUN_TIMEOUT_S = 60.0
_PER_TRY_WAIT_S = (
    _AGENT_RUN_TIMEOUT_S + SHUTDOWN_DRAIN_S + harness_mod._HARNESS_WAIT_BUFFER_S
)
_UNDER_DEADLINE_S = 10.0
_FINAL_TRY = 2


def _queued_record(attempts: int) -> str:
    return json.dumps(
        {
            "run_id": _INCIDENT_RUN_ID,
            "incident_id": _INCIDENT_RUN_ID,
            "attempts": attempts,
            "retry_queued": True,
        }
    )


def _final_record(attempts: int) -> str:
    return json.dumps(
        {
            "run_id": retry_run_id(_INCIDENT_RUN_ID, attempts),
            "incident_id": _INCIDENT_RUN_ID,
            "attempts": attempts,
            "retry_queued": False,
        }
    )


def _fake_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "s")
    monkeypatch.setattr(harness_mod, "_build_fault_event", lambda *a, **k: {})

    def _response(body: dict) -> MagicMock:
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value=body)
        return resp

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            return _response({"status": "ok", "run_timeout_s": _AGENT_RUN_TIMEOUT_S})

        async def post(self, url, **kwargs):
            return _response({"run_id": _INCIDENT_RUN_ID})

    monkeypatch.setattr(harness_mod.httpx, "AsyncClient", FakeClient)


def _fake_loop_clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [0.0]

    class FakeLoop:
        def time(self) -> float:
            return now[0]

    monkeypatch.setattr(harness_mod.asyncio, "get_event_loop", lambda: FakeLoop())
    return now


async def _wait(runs_dir: Path) -> Path:
    return await trigger_and_wait(
        scenario_id="k8s-rollback-1",
        seed=1,
        orchestrator_url="http://localhost:9099",
        runs_dir=runs_dir,
        model="test-model",
    )


async def test_trigger_and_wait_follows_queued_tries_to_the_final_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_orchestrator(monkeypatch)
    writes = [
        (tmp_path / f"{_INCIDENT_RUN_ID}.json", _queued_record(1)),
        (
            tmp_path / f"{retry_run_id(_INCIDENT_RUN_ID, _FINAL_TRY)}.json",
            _final_record(_FINAL_TRY),
        ),
    ]

    async def fake_sleep(t):
        if writes:
            path, body = writes.pop(0)
            path.write_text(body)

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    result = await _wait(tmp_path)

    assert result == tmp_path / f"{retry_run_id(_INCIDENT_RUN_ID, _FINAL_TRY)}.json"


async def test_trigger_and_wait_gives_each_try_its_own_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_orchestrator(monkeypatch)
    now = _fake_loop_clock(monkeypatch)
    first = tmp_path / f"{_INCIDENT_RUN_ID}.json"
    final = tmp_path / f"{retry_run_id(_INCIDENT_RUN_ID, _FINAL_TRY)}.json"

    async def fake_sleep(t):
        now[0] += t
        if not first.exists() and now[0] >= _PER_TRY_WAIT_S - _UNDER_DEADLINE_S:
            first.write_text(_queued_record(1))
        elif first.exists() and now[0] >= 2 * (_PER_TRY_WAIT_S - _UNDER_DEADLINE_S):
            final.write_text(_final_record(_FINAL_TRY))

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    assert await _wait(tmp_path) == final


async def test_trigger_and_wait_rereads_a_partly_written_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_orchestrator(monkeypatch)
    result_file = tmp_path / f"{_INCIDENT_RUN_ID}.json"
    bodies = ["{", json.dumps({"run_id": _INCIDENT_RUN_ID})]

    async def fake_sleep(t):
        if bodies:
            result_file.write_text(bodies.pop(0))

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    assert await _wait(tmp_path) == result_file


async def test_trigger_and_wait_removes_stale_retry_records_and_traces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake_orchestrator(monkeypatch)
    stale = [
        tmp_path / f"{retry_run_id(_INCIDENT_RUN_ID, n)}{suffix}"
        for n in range(_FINAL_TRY, MAX_TRIES + 1)
        for suffix in (".json", "_trace.jsonl")
    ]
    for path in stale:
        path.write_text(_final_record(_FINAL_TRY))
    first = tmp_path / f"{_INCIDENT_RUN_ID}.json"
    first.write_text(_final_record(_FINAL_TRY))
    seen_on_first_poll: list[bool] = []

    async def fake_sleep(t):
        if not seen_on_first_poll:
            seen_on_first_poll.extend(p.exists() for p in [first, *stale])
            first.write_text(_queued_record(1))
        else:
            stale[0].write_text(_final_record(_FINAL_TRY))

    monkeypatch.setattr(harness_mod.asyncio, "sleep", fake_sleep)

    assert await _wait(tmp_path) == stale[0]
    assert not any(seen_on_first_poll)
