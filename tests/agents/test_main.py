from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("LLM_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("LLM_API_KEY", "sk-test")
os.environ.setdefault("VIGIL_WEBHOOK_SECRET", "test-secret")

from fastapi import FastAPI
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
    new_app.state.ssh_mcp = AsyncMock()
    new_app.state.nixos_mcp = AsyncMock()
    new_app.state.git_mcp = AsyncMock()
    return new_app


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
