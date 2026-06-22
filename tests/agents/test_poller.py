"""Unit tests for orchestrator.poller - alert polling and FaultEvent mapping."""

from __future__ import annotations

import asyncio
import inspect
import logging
import types
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from common.constants import POLLER_UNHEALTHY_AFTER
from orchestrator.agent import run_orchestration
from orchestrator.models import FaultEvent

# These imports will fail until poller.py is created - that is the RED gate.
from orchestrator.poller import _alert_to_fault_event, prometheus_poller


def _app_with_state() -> types.SimpleNamespace:
    return types.SimpleNamespace(state=types.SimpleNamespace())


SAMPLE_ALERT = {
    "labels": {"alertname": "HighMemory", "namespace": "default", "pod": "myapp-abc"},
    "annotations": {"summary": "Memory usage above 90%"},
    "state": "firing",
    "activeAt": "2026-04-24T10:00:00Z",
    "value": "0.92",
    "fingerprint": "abc123",
}


def test_alert_to_fault_event_constructs_valid_model():
    event = _alert_to_fault_event(SAMPLE_ALERT)
    assert isinstance(event, FaultEvent)
    assert event.receiver == "prometheus-poller"
    assert event.status == "firing"
    assert len(event.alerts) == 1
    assert event.alerts[0]["fingerprint"] == "abc123"
    assert event.commonLabels["alertname"] == "HighMemory"
    assert event.groupLabels["alertname"] == "HighMemory"
    assert event.version == "4"


def test_alert_to_fault_event_handles_missing_fingerprint():
    alert = dict(SAMPLE_ALERT)
    del alert["fingerprint"]
    event = _alert_to_fault_event(alert)
    assert event.alerts[0]["fingerprint"] == ""


def test_alert_to_fault_event_handles_missing_labels():
    alert = {"state": "firing", "activeAt": "2026-04-24T10:00:00Z"}
    event = _alert_to_fault_event(alert)
    assert isinstance(event, FaultEvent)
    assert event.commonLabels == {}


@pytest.mark.asyncio
async def test_poller_disabled_when_env_false(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "false")
    app = MagicMock()
    with patch("orchestrator.poller.httpx.AsyncClient") as mock_client:
        await prometheus_poller(app)
        mock_client.assert_not_called()


@pytest.mark.asyncio
async def test_poller_skips_resolved_alerts(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    resolved_alert = dict(SAMPLE_ALERT)
    resolved_alert["state"] = "resolved"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"alerts": [resolved_alert]}}

    app = MagicMock()

    sleep_side = [None, asyncio.CancelledError]
    run_patch = patch("orchestrator.poller.run_orchestration", new_callable=AsyncMock)
    client_patch = patch("orchestrator.poller.httpx.AsyncClient")
    sleep_patch = patch("orchestrator.poller.asyncio.sleep", side_effect=sleep_side)
    with run_patch as mock_run, client_patch as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        with sleep_patch:
            try:
                await prometheus_poller(app)
            except asyncio.CancelledError:
                pass
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_poller_deduplicates_by_fingerprint(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")
    monkeypatch.setenv("PROM_HANDLED_TTL_S", "600")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"alerts": [SAMPLE_ALERT]}}

    app = MagicMock()
    app.state.kubectl_mcp = MagicMock()
    app.state.flux_mcp = MagicMock()
    app.state.nixos_mcp = MagicMock()

    run_patch = patch("orchestrator.poller.run_orchestration", new_callable=AsyncMock)
    client_patch = patch("orchestrator.poller.httpx.AsyncClient")
    sleep_calls = [None, None, asyncio.CancelledError]
    sleep_patch = patch("orchestrator.poller.asyncio.sleep", side_effect=sleep_calls)
    with run_patch as mock_run, client_patch as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        with sleep_patch:
            try:
                await prometheus_poller(app)
            except asyncio.CancelledError:
                pass
        assert mock_run.call_count <= 1


@pytest.mark.asyncio
async def test_poller_passes_all_mcp_servers_to_run_orchestration(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"data": {"alerts": [SAMPLE_ALERT]}}

    app = MagicMock()
    app.state.kubectl_mcp = MagicMock()
    app.state.flux_mcp = MagicMock()
    app.state.nixos_mcp = MagicMock()
    app.state.git_mcp = MagicMock()

    run_patch = patch("orchestrator.poller.run_orchestration", new_callable=AsyncMock)
    client_patch = patch("orchestrator.poller.httpx.AsyncClient")
    sleep_calls = [None, asyncio.CancelledError]
    sleep_patch = patch("orchestrator.poller.asyncio.sleep", side_effect=sleep_calls)
    with run_patch as mock_run, client_patch as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(return_value=mock_response)
        with sleep_patch:
            try:
                await prometheus_poller(app)
            except asyncio.CancelledError:
                pass

    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert "git_mcp" in kwargs
    sig = inspect.signature(run_orchestration)
    sig.bind(*args, **kwargs)


@pytest.mark.asyncio
async def test_poller_continues_after_http_error(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    app = MagicMock()

    with patch("orchestrator.poller.httpx.AsyncClient") as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(
            side_effect=[
                httpx.ConnectError("connection refused"),
                asyncio.CancelledError,
            ]
        )
        with patch("orchestrator.poller.asyncio.sleep", return_value=None):
            try:
                await prometheus_poller(app)
            except asyncio.CancelledError:
                pass


def _http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://prom/api/v1/alerts")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("unauthorized", request=request, response=response)


async def _drive_poller(app, get_side_effect, sleep_side) -> None:
    client_patch = patch("orchestrator.poller.httpx.AsyncClient")
    sleep_patch = patch("orchestrator.poller.asyncio.sleep", side_effect=sleep_side)
    with client_patch as MockClient:
        instance = MockClient.return_value.__aenter__.return_value
        instance.get = AsyncMock(side_effect=get_side_effect)
        with sleep_patch:
            try:
                await prometheus_poller(app)
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_consecutive_failures_flip_detection_to_degraded(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    app = _app_with_state()
    errors = [httpx.ConnectError("refused")] * POLLER_UNHEALTHY_AFTER
    sleep_side = [None] * POLLER_UNHEALTHY_AFTER + [asyncio.CancelledError]
    await _drive_poller(app, errors + [asyncio.CancelledError], sleep_side)

    assert app.state.poller_health["consecutive_failures"] >= POLLER_UNHEALTHY_AFTER
    assert app.state.poller_health["last_success_at"] is None


@pytest.mark.asyncio
async def test_success_resets_failures_and_sets_timestamp(monkeypatch):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    ok_response = MagicMock()
    ok_response.raise_for_status = MagicMock()
    ok_response.json.return_value = {"data": {"alerts": []}}

    app = _app_with_state()
    get_side = [httpx.ConnectError("refused"), ok_response, asyncio.CancelledError]
    sleep_side = [None, None, asyncio.CancelledError]
    await _drive_poller(app, get_side, sleep_side)

    assert app.state.poller_health["consecutive_failures"] == 0
    assert app.state.poller_health["last_success_at"] is not None


@pytest.mark.asyncio
async def test_auth_failure_logged_at_error(monkeypatch, caplog):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    app = _app_with_state()
    get_side = [_http_status_error(401), asyncio.CancelledError]
    sleep_side = [None, asyncio.CancelledError]
    with caplog.at_level(logging.WARNING, logger="vigil.orchestrator.poller"):
        await _drive_poller(app, get_side, sleep_side)

    records = [r for r in caplog.records if "prometheus query" in r.message]
    assert records
    assert all(r.levelno == logging.ERROR for r in records)


@pytest.mark.asyncio
async def test_transient_failure_logged_at_warning(monkeypatch, caplog):
    monkeypatch.setenv("PROM_POLLER_ENABLED", "true")
    monkeypatch.setenv("PROM_POLL_INTERVAL_S", "0")

    app = _app_with_state()
    get_side = [httpx.ConnectError("refused"), asyncio.CancelledError]
    sleep_side = [None, asyncio.CancelledError]
    with caplog.at_level(logging.WARNING, logger="vigil.orchestrator.poller"):
        await _drive_poller(app, get_side, sleep_side)

    records = [r for r in caplog.records if "prometheus query" in r.message]
    assert records
    assert all(r.levelno == logging.WARNING for r in records)
