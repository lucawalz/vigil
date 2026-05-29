from __future__ import annotations

import asyncio
import logging
import os
import time

import httpx

from .agent import run_orchestration
from .models import FaultEvent

log = logging.getLogger("vigil.orchestrator.poller")

_DEFAULT_PROM_URL = "http://10.0.0.10:9090"


def log_task_exception(task: asyncio.Task, logger: logging.Logger) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background orchestration task failed: %s", exc, exc_info=exc)


def _alert_to_fault_event(alert: dict) -> FaultEvent:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    prom_url = os.environ.get("PROMETHEUS_URL", _DEFAULT_PROM_URL)
    return FaultEvent(
        receiver="prometheus-poller",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": labels,
                "annotations": annotations,
                "startsAt": alert.get("activeAt", ""),
                "endsAt": "",
                "generatorURL": "",
                "fingerprint": alert.get("fingerprint", ""),
            }
        ],
        groupLabels={"alertname": labels.get("alertname", "unknown")},
        commonLabels=labels,
        commonAnnotations=annotations,
        externalURL=prom_url,
        version="4",
        groupKey=f"poller/{labels.get('alertname', 'unknown')}",
        truncatedAlerts=0,
    )


async def prometheus_poller(app) -> None:
    enabled = os.environ.get("PROM_POLLER_ENABLED", "true").lower() == "true"
    if not enabled:
        log.info("poller: disabled (PROM_POLLER_ENABLED=false)")
        return

    poll_interval = int(os.environ.get("PROM_POLL_INTERVAL_S", "120"))
    prom_url = os.environ.get("PROMETHEUS_URL", _DEFAULT_PROM_URL)
    handled_ttl = int(os.environ.get("PROM_HANDLED_TTL_S", "600"))
    model_name = os.environ.get("LLM_MODEL_NAME", "unknown")
    handled: dict[str, float] = {}
    _active_tasks: set[asyncio.Task] = set()

    async with httpx.AsyncClient() as client:
        while True:
            await asyncio.sleep(poll_interval)
            now = time.monotonic()
            handled = {k: v for k, v in handled.items() if v > now}

            try:
                r = await client.get(f"{prom_url}/api/v1/alerts", timeout=10)
                r.raise_for_status()
                alerts = r.json().get("data", {}).get("alerts", [])
            except Exception as exc:
                log.warning("poller: prometheus query failed: %s", exc)
                continue

            for alert in alerts:
                if alert.get("state") != "firing":
                    continue
                fp = alert.get("fingerprint") or str(alert.get("labels", {}))
                if fp in handled:
                    continue
                handled[fp] = now + handled_ttl
                event = _alert_to_fault_event(alert)
                log.info(
                    "poller: detected firing alert %s fingerprint=%s",
                    alert.get("labels", {}).get("alertname", "?"),
                    fp,
                )
                task = asyncio.create_task(
                    run_orchestration(
                        event,
                        kubectl_mcp=app.state.kubectl_mcp,
                        flux_mcp=app.state.flux_mcp,
                        nixos_mcp=app.state.nixos_mcp,
                        git_mcp=app.state.git_mcp,
                        scenario="autonomous",
                        seed=None,
                        model_name=model_name,
                    )
                )
                _active_tasks.add(task)
                task.add_done_callback(_active_tasks.discard)
                task.add_done_callback(lambda t: log_task_exception(t, log))
