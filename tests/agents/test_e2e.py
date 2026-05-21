from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from unittest.mock import AsyncMock

import httpx
import pytest

os.environ.setdefault("LLM_MODEL_NAME", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:1/v1")
os.environ.setdefault("OLLAMA_API_KEY", "sk-test")
os.environ.setdefault("VIGIL_WEBHOOK_SECRET", "e2e-secret")

from diagnosis.models import DiagnosisReport
from fastapi import FastAPI
from orchestrator import agent as orch_mod
from orchestrator import main as main_mod
from pydantic_ai.usage import Usage
from remediation.models import RemediationResult
from watchdog.models import HealthSnapshot, WatchdogResult

pytestmark = pytest.mark.slow


def _canned_report() -> DiagnosisReport:
    return DiagnosisReport(
        root_cause="wrong image tag",
        root_cause_component="vigil-app:bad-tag-v9",
        severity="high",
        affected_resources=["default/vigil-app"],
        evidence="Failed to pull image vigil-app:bad-tag-v9",
        drift_classification="declared_drift",
        recommended_action="git_commit_k8s",
        confidence=0.95,
    )


def _canned_remediation() -> RemediationResult:
    return RemediationResult(
        success=True,
        actions_taken=[
            "create_branch",
            "write_manifest",
            "commit_files",
            "push_branch",
            "create_pr",
            "wait_for_gate",
            "reconcile_kustomization",
        ],
        tool_calls_count=7,
        destructive_repair=False,
    )


def _canned_snap() -> HealthSnapshot:
    return HealthSnapshot(
        ready_pods=3,
        total_pods=3,
        endpoints_healthy=True,
        captured_at="2026-04-18T10:00:00Z",
    )


async def test_webhook_to_audit_log_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EVAL_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("VIGIL_WEBHOOK_SECRET", "e2e-secret")
    monkeypatch.setattr(
        orch_mod,
        "run_diagnosis",
        AsyncMock(
            return_value=(
                _canned_report(),
                Usage(input_tokens=100, output_tokens=50),
                [],
            )
        ),
    )
    monkeypatch.setattr(
        orch_mod,
        "capture_health_snapshot",
        AsyncMock(return_value=_canned_snap()),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_remediation",
        AsyncMock(
            return_value=(
                _canned_remediation(),
                Usage(input_tokens=200, output_tokens=80),
                [],
            )
        ),
    )
    monkeypatch.setattr(
        orch_mod,
        "run_watchdog",
        AsyncMock(return_value=WatchdogResult(degraded=False, snapshot=_canned_snap())),
    )

    @asynccontextmanager
    async def _noop_lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield

    test_app = FastAPI(lifespan=_noop_lifespan)
    test_app.get("/healthz")(main_mod.healthz)
    test_app.post("/webhook", dependencies=main_mod.app.routes[-1].dependencies)(
        main_mod.webhook
    )
    test_app.state.kubectl_mcp = AsyncMock()
    test_app.state.flux_mcp = AsyncMock()
    test_app.state.ssh_mcp = AsyncMock()
    test_app.state.nixos_mcp = AsyncMock()
    test_app.state.git_mcp = AsyncMock()

    payload = {
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
                    "pod": "vigil-app-e2e",
                },
                "annotations": {"description": "Pod is in CrashLoopBackOff"},
                "startsAt": "2026-04-18T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": "http://prometheus/graph",
                "fingerprint": "e2e123",
            }
        ],
    }

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/webhook",
            json=payload,
            headers={"Authorization": "Bearer e2e-secret"},
        )
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    pending = {t for t in asyncio.all_tasks() if t is not asyncio.current_task()}
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    written = (tmp_path / "runs" / f"{run_id}.json").read_text()
    assert json.loads(written)["outcome"] == "success"

    index_lines = (tmp_path / "runs_index.jsonl").read_text().strip().splitlines()
    assert len(index_lines) == 1
