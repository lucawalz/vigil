from __future__ import annotations

import asyncio
import os
import re
import subprocess
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")
os.environ.setdefault("VIGIL_WEBHOOK_SECRET", "test-secret")

from common.constants import (
    GATE_REVERT_CALL_TIMEOUT_S,
    GATE_WAIT_TIMEOUT_MAX_S,
    GATE_WAIT_TIMEOUT_MIN_S,
    GATE_WAIT_TIMEOUT_S,
    GIT_MCP_GATE_FINALISER_S,
    GIT_MCP_GATE_POLL_INTERVAL_S,
    GIT_MCP_READ_TIMEOUT_S,
    LLM_MAX_RETRIES,
    LLM_REQUEST_TIMEOUT_S,
    MCP_CALL_TIMEOUT_S,
    ROLLBACK_VERIFY_WINDOW_S,
    SHUTDOWN_DRAIN_S,
    SHUTDOWN_STOP_MARGIN_S,
    SHUTDOWN_STOP_TIMEOUT_S,
)
from fastapi import FastAPI
from orchestrator import agent as orch_mod
from orchestrator import main as main_mod
from orchestrator.models import RunRecord


def _canned_record() -> RunRecord:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return RunRecord(
        run_id="k8s-1_seed-20260418T100000Z_test-model_deadbee",
        scenario="k8s-1",
        seed="seed-20260418T100000Z",
        model="test-model",
        git_sha7="deadbee",
        started_at=now,
        ended_at=now,
        outcome="success",
        success_rate=True,
        diagnosis_accuracy=None,
        MTTR_s=1.0,
        destructive_repair=False,
        rollback_triggered=False,
        rollback_success=None,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tool_calls=2,
        iteration_count=2,
        autonomy_level="full",
        actions_taken=[],
    )


def _alertmanager_payload() -> dict:
    return {
        "version": "4",
        "groupKey": '{}:{alertname="KubePodCrashLooping"}',
        "status": "firing",
        "receiver": "vigil-webhook",
        "groupLabels": {"alertname": "KubePodCrashLooping"},
        "commonLabels": {"namespace": "default"},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager.monitoring:9093",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodCrashLooping",
                    "namespace": "default",
                    "pod": "vigil-app-abc123",
                },
                "annotations": {"description": "Pod is in CrashLoopBackOff"},
                "startsAt": "2026-04-18T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus/graph",
                "fingerprint": "abc123",
            }
        ],
    }


@pytest.fixture
def test_app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """Build a FastAPI app that skips MCP boot and stubs state with mocks."""
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "test-secret")

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    new_app = FastAPI(title="Vigil Orchestrator (test)", lifespan=_noop_lifespan)
    new_app.get("/healthz")(main_mod.healthz)
    new_app.post("/webhook", dependencies=main_mod.app.routes[-1].dependencies)(
        main_mod.webhook
    )
    # ASGITransport does not fire lifespan events, so seed app.state directly.
    new_app.state.kubectl_mcp = AsyncMock()
    new_app.state.flux_mcp = AsyncMock()
    new_app.state.nixos_mcp = AsyncMock()
    new_app.state.git_mcp = AsyncMock()
    return new_app


async def test_lifespan_rejects_an_unknown_eval_target_at_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIGIL_EVAL_TARGET", "laptop")
    with pytest.raises(ValueError, match="VIGIL_EVAL_TARGET"):
        async with main_mod.lifespan(main_mod.app):
            pass


class _RecordingMCPServer:
    def __init__(self, servers: list[dict], **kwargs: object) -> None:
        servers.append(kwargs)

    async def __aenter__(self) -> _RecordingMCPServer:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.fixture
def recorded_servers(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    servers: list[dict] = []
    monkeypatch.delenv("VIGIL_EVAL_TARGET", raising=False)
    for server in ("KUBECTL", "FLUX", "NIXOS", "GIT"):
        monkeypatch.delenv(f"{server}_MCP_CMD", raising=False)
    monkeypatch.setattr(main_mod, "_configure_logging", lambda: None)
    monkeypatch.setattr(main_mod, "prometheus_poller", AsyncMock())
    monkeypatch.setattr(
        main_mod,
        "MCPServerStdio",
        lambda **kwargs: _RecordingMCPServer(servers, **kwargs),
    )
    return servers


def test_gate_wait_budget_derives_from_the_gate_wait_timeout() -> None:
    assert GIT_MCP_READ_TIMEOUT_S == (
        GATE_WAIT_TIMEOUT_S + GIT_MCP_GATE_FINALISER_S + GIT_MCP_GATE_POLL_INTERVAL_S
    )
    assert GATE_REVERT_CALL_TIMEOUT_S == GIT_MCP_READ_TIMEOUT_S + MCP_CALL_TIMEOUT_S
    assert GATE_WAIT_TIMEOUT_S < GIT_MCP_READ_TIMEOUT_S < GATE_REVERT_CALL_TIMEOUT_S


def test_gate_wait_budget_check_passes_with_defaults() -> None:
    main_mod._check_gate_wait_budget()


def _attempt_s() -> float:
    return (
        main_mod.DIAGNOSIS_TIMEOUT_S
        + main_mod.REMEDIATION_TIMEOUT_S
        + GIT_MCP_READ_TIMEOUT_S
        + 2 * MCP_CALL_TIMEOUT_S
        + main_mod.WATCHDOG_WINDOW_S
    )


def test_gate_wait_budget_check_fits_one_attempt_in_the_run_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "ORCHESTRATOR_RUN_TIMEOUT_S", _attempt_s() + 1)
    main_mod._check_gate_wait_budget()

    monkeypatch.setattr(main_mod, "ORCHESTRATOR_RUN_TIMEOUT_S", _attempt_s())
    with pytest.raises(
        ValueError, match="WATCHDOG_WINDOW_S.*ORCHESTRATOR_RUN_TIMEOUT_S"
    ):
        main_mod._check_gate_wait_budget()


def test_gate_wait_budget_check_passes_with_agent_env_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "DIAGNOSIS_TIMEOUT_S", 600.0)
    monkeypatch.setattr(main_mod, "REMEDIATION_TIMEOUT_S", 540.0)
    monkeypatch.setattr(main_mod, "ORCHESTRATOR_RUN_TIMEOUT_S", 2400.0)
    main_mod._check_gate_wait_budget()


def test_gate_wait_budget_check_covers_the_llm_retry_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retry_budget_s = (1 + LLM_MAX_RETRIES) * LLM_REQUEST_TIMEOUT_S
    monkeypatch.setattr(main_mod, "REMEDIATION_TIMEOUT_S", retry_budget_s + 1)
    main_mod._check_gate_wait_budget()

    monkeypatch.setattr(main_mod, "REMEDIATION_TIMEOUT_S", retry_budget_s)
    with pytest.raises(
        ValueError, match="LLM_REQUEST_TIMEOUT_S.*REMEDIATION_TIMEOUT_S"
    ):
        main_mod._check_gate_wait_budget()


@pytest.mark.parametrize(
    "gate_wait_s", [GATE_WAIT_TIMEOUT_MIN_S - 1, GATE_WAIT_TIMEOUT_MAX_S + 1]
)
def test_gate_wait_budget_check_rejects_gate_wait_outside_git_mcp_bounds(
    gate_wait_s: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_mod, "GATE_WAIT_TIMEOUT_S", gate_wait_s)
    with pytest.raises(ValueError, match=f"GATE_WAIT_TIMEOUT_S.*{gate_wait_s}"):
        main_mod._check_gate_wait_budget()


def test_gate_wait_budget_check_rejects_read_timeout_not_above_gate_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "GIT_MCP_READ_TIMEOUT_S", GATE_WAIT_TIMEOUT_S)
    with pytest.raises(ValueError, match="GATE_WAIT_TIMEOUT_S.*GIT_MCP_READ_TIMEOUT_S"):
        main_mod._check_gate_wait_budget()


def test_gate_wait_budget_check_rejects_revert_call_not_above_read_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main_mod, "GATE_REVERT_CALL_TIMEOUT_S", GIT_MCP_READ_TIMEOUT_S)
    with pytest.raises(
        ValueError, match="GIT_MCP_READ_TIMEOUT_S.*GATE_REVERT_CALL_TIMEOUT_S"
    ):
        main_mod._check_gate_wait_budget()


def test_gate_wait_budget_check_fits_the_rollback_in_its_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rollback_s = (
        GATE_REVERT_CALL_TIMEOUT_S + MCP_CALL_TIMEOUT_S + ROLLBACK_VERIFY_WINDOW_S
    )
    monkeypatch.setattr(main_mod, "ROLLBACK_TIMEOUT_S", rollback_s)
    main_mod._check_gate_wait_budget()

    monkeypatch.setattr(main_mod, "ROLLBACK_TIMEOUT_S", rollback_s - 1)
    with pytest.raises(
        ValueError, match="ROLLBACK_VERIFY_WINDOW_S.*ROLLBACK_TIMEOUT_S"
    ):
        main_mod._check_gate_wait_budget()


_LOW_GATE_WAIT_S = "180"
_RAISED_MCP_CALL_TIMEOUT_S = "200"
_BUDGET_CHECK = (
    "from orchestrator.main import _check_gate_wait_budget; _check_gate_wait_budget()"
)


def test_gate_wait_budget_check_fits_the_shutdown_drain_in_the_stop_timeout() -> None:
    assert SHUTDOWN_DRAIN_S + SHUTDOWN_STOP_MARGIN_S <= SHUTDOWN_STOP_TIMEOUT_S
    env = {
        **os.environ,
        "GATE_WAIT_TIMEOUT_S": _LOW_GATE_WAIT_S,
        "MCP_CALL_TIMEOUT_S": _RAISED_MCP_CALL_TIMEOUT_S,
    }
    result = subprocess.run(
        [sys.executable, "-c", _BUDGET_CHECK],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert re.search(
        r"SHUTDOWN_DRAIN_S \+ SHUTDOWN_STOP_MARGIN_S.*SHUTDOWN_STOP_TIMEOUT_S",
        result.stderr,
    )


async def test_lifespan_checks_the_gate_wait_budget_before_starting_servers(
    recorded_servers: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(main_mod, "ORCHESTRATOR_RUN_TIMEOUT_S", _attempt_s())
    with pytest.raises(ValueError, match="ORCHESTRATOR_RUN_TIMEOUT_S"):
        async with main_mod.lifespan(FastAPI()):
            pass
    assert recorded_servers == []


async def test_lifespan_bounds_git_mcp_requests_by_the_gate_wait_budget(
    recorded_servers: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GATE_WAIT_TIMEOUT_S", raising=False)
    async with main_mod.lifespan(FastAPI()):
        pass

    by_command = {server["command"]: server for server in recorded_servers}
    git_server = by_command["git-mcp"]
    assert git_server["read_timeout"] == GIT_MCP_READ_TIMEOUT_S
    assert git_server["env"]["GATE_WAIT_TIMEOUT_S"] == str(GATE_WAIT_TIMEOUT_S)
    for command in ("kubectl-mcp", "flux-mcp", "nixos-mcp"):
        assert "read_timeout" not in by_command[command]
        assert "GATE_WAIT_TIMEOUT_S" not in by_command[command]["env"]


_DRAIN_WORK_S = 0.05
_TEST_WAIT_S = 5.0
_MCP_SERVER_COUNT = 4


class _ClosingMCPServer:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    async def __aenter__(self) -> _ClosingMCPServer:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self._events.append("exit")


async def test_lifespan_drains_active_runs_before_closing_servers(
    recorded_servers: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    monkeypatch.setattr(
        main_mod, "MCPServerStdio", lambda **_kwargs: _ClosingMCPServer(events)
    )
    started = asyncio.Event()

    async def rolling_back_run() -> RunRecord:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            events.append("cancelled")
            await asyncio.sleep(_DRAIN_WORK_S)
            events.append("rolled back")
            raise
        return _canned_record()

    async with main_mod.lifespan(FastAPI()):
        orch_mod.track_run(asyncio.create_task(rolling_back_run()))
        await asyncio.wait_for(started.wait(), _TEST_WAIT_S)

    assert events[:2] == ["cancelled", "rolled back"]
    assert events[2:] == ["exit"] * _MCP_SERVER_COUNT


async def test_healthz_returns_ok_with_detection_fields(test_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["detection"] == "ok"
    assert body["consecutive_failures"] == 0
    assert body["last_success_at"] is None


async def test_healthz_reports_degraded_when_poller_unhealthy(
    test_app: FastAPI,
) -> None:
    from common.constants import POLLER_UNHEALTHY_AFTER

    test_app.state.poller_health = {
        "consecutive_failures": POLLER_UNHEALTHY_AFTER,
        "last_success_at": "2026-05-30T00:00:00Z",
    }
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["detection"] == "degraded"
    assert body["consecutive_failures"] == POLLER_UNHEALTHY_AFTER


async def test_healthz_reports_the_run_timeout(test_app: FastAPI) -> None:
    from orchestrator.agent import ORCHESTRATOR_RUN_TIMEOUT_S

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/healthz")
    assert r.json()["run_timeout_s"] == ORCHESTRATOR_RUN_TIMEOUT_S


async def test_webhook_rejects_missing_auth(test_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/webhook", json=_alertmanager_payload())
    assert r.status_code == 401


async def test_webhook_rejects_wrong_bearer(test_app: FastAPI) -> None:
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer wrong-secret"},
        )
    assert r.status_code == 401


async def test_webhook_happy_path(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        main_mod, "run_orchestration", AsyncMock(return_value=_canned_record())
    )
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["run_id"].startswith("k8s-1_seed-")


async def test_webhook_rejects_empty_alerts_array(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        main_mod, "run_orchestration", AsyncMock(return_value=_canned_record())
    )
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json={"version": "4", "alerts": []},
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 400


async def test_webhook_default_scenario(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_run = AsyncMock(return_value=_canned_record())
    monkeypatch.setattr(main_mod, "run_orchestration", mock_run)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    assert mock_run.call_args.kwargs["scenario"] == "k8s-1"
    assert mock_run.call_args.kwargs["seed"] is None


async def test_webhook_scenario_query_param(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_run = AsyncMock(return_value=_canned_record())
    monkeypatch.setattr(main_mod, "run_orchestration", mock_run)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            params={"scenario": "k8s-3"},
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    assert mock_run.call_args.kwargs["scenario"] == "k8s-3"


async def test_webhook_seed_query_param(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_run = AsyncMock(return_value=_canned_record())
    monkeypatch.setattr(main_mod, "run_orchestration", mock_run)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            params={"scenario": "k8s-1", "seed": 5},
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    assert mock_run.call_args.kwargs["scenario"] == "k8s-1"
    assert mock_run.call_args.kwargs["seed"] == 5
    assert isinstance(mock_run.call_args.kwargs["seed"], int)


async def test_webhook_returns_run_id_and_outcome(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        main_mod, "run_orchestration", AsyncMock(return_value=_canned_record())
    )
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body


async def test_webhook_blocks_alert_trigger_when_toggle_enabled(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_BLOCK_ALERT_TRIGGERS", "true")
    mock_run = AsyncMock(return_value=_canned_record())
    monkeypatch.setattr(main_mod, "run_orchestration", mock_run)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
    mock_run.assert_not_called()


async def test_webhook_allows_eval_trigger_when_toggle_enabled(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("VIGIL_BLOCK_ALERT_TRIGGERS", "true")
    mock_run = AsyncMock(return_value=_canned_record())
    monkeypatch.setattr(main_mod, "run_orchestration", mock_run)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            params={"scenario": "k8s-1", "seed": 5, "model": "test-model"},
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    assert "run_id" in r.json()
    mock_run.assert_called_once()


async def test_webhook_allows_alert_trigger_when_toggle_unset(
    test_app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("VIGIL_BLOCK_ALERT_TRIGGERS", raising=False)
    mock_run = AsyncMock(return_value=_canned_record())
    monkeypatch.setattr(main_mod, "run_orchestration", mock_run)
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=_alertmanager_payload(),
            headers={"Authorization": "Bearer test-secret"},
        )
    assert r.status_code == 200
    assert "run_id" in r.json()
    mock_run.assert_called_once()
