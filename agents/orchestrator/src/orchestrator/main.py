from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from common.constants import POLLER_UNHEALTHY_AFTER
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_ai.mcp import MCPServerStdio

from .agent import build_run_id, run_orchestration
from .models import FaultEvent
from .poller import log_task_exception, prometheus_poller

log = logging.getLogger("vigil.orchestrator")


def _configure_logging() -> None:
    level = logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO").upper())
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(name)-35s %(levelname)-8s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
    )
    vigil_log = logging.getLogger("vigil")
    vigil_log.setLevel(level)
    vigil_log.addHandler(handler)
    vigil_log.propagate = False


def _mcp_commands() -> dict[str, list[str]]:
    return {
        "kubectl": os.environ.get("KUBECTL_MCP_CMD", "kubectl-mcp").split(),
        "flux": os.environ.get("FLUX_MCP_CMD", "flux-mcp").split(),
        "nixos": os.environ.get("NIXOS_MCP_CMD", "nixos-mcp").split(),
        "git": os.environ.get("GIT_MCP_CMD", "git-mcp").split(),
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    cmds = _mcp_commands()
    # MCPServerStdio defaults env=None which gives child processes an empty
    # environment, breaking KUBECONFIG, PATH, etc.
    env = os.environ.copy()

    kubectl_argv = cmds["kubectl"]
    flux_argv = cmds["flux"]
    nixos_argv = cmds["nixos"]
    git_argv = cmds["git"]

    async with (
        MCPServerStdio(
            command=kubectl_argv[0], args=kubectl_argv[1:], env=env, max_retries=3
        ) as kubectl_mcp,
        MCPServerStdio(command=flux_argv[0], args=flux_argv[1:], env=env) as flux_mcp,
        MCPServerStdio(
            command=nixos_argv[0], args=nixos_argv[1:], env=env
        ) as nixos_mcp,
        MCPServerStdio(
            command=git_argv[0], args=git_argv[1:], env=env, max_retries=3
        ) as git_mcp,
    ):
        app.state.kubectl_mcp = kubectl_mcp
        app.state.flux_mcp = flux_mcp
        app.state.nixos_mcp = nixos_mcp
        app.state.git_mcp = git_mcp
        log.info("MCP servers booted: kubectl, flux, nixos, git")
        poll_task = asyncio.create_task(prometheus_poller(app))
        yield
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            pass
        log.info("MCP servers shutting down")


_TRUTHY = {"true", "1", "yes"}


def _alert_triggers_blocked() -> bool:
    value = os.environ.get("VIGIL_BLOCK_ALERT_TRIGGERS", "false")
    return value.strip().lower() in _TRUTHY


def _is_eval_triggered(request: Request) -> bool:
    return "model" in request.query_params


_bearer = HTTPBearer(auto_error=False)


def _check_auth(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> None:
    expected = os.environ.get("VIGIL_WEBHOOK_SECRET", "")
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VIGIL_WEBHOOK_SECRET not configured",
        )
    bad = (
        creds is None
        or creds.scheme.lower() != "bearer"
        or creds.credentials != expected
    )
    if bad:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


app = FastAPI(title="Vigil Orchestrator", lifespan=lifespan)

# Holds references to in-flight background tasks so they are not GC'd.
_active_tasks: set[asyncio.Task] = set()


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, object]:
    health = getattr(request.app.state, "poller_health", None) or {}
    consecutive_failures = health.get("consecutive_failures", 0)
    detection = "degraded" if consecutive_failures >= POLLER_UNHEALTHY_AFTER else "ok"
    return {
        "status": "ok",
        "detection": detection,
        "consecutive_failures": consecutive_failures,
        "last_success_at": health.get("last_success_at"),
    }


@app.post("/webhook", dependencies=[Depends(_check_auth)])
async def webhook(
    request: Request,
    scenario: str = "k8s-1",
    seed: int | None = None,
    model: str | None = None,
) -> dict[str, str]:
    if _alert_triggers_blocked() and not _is_eval_triggered(request):
        log.info("ignoring alert-triggered run: VIGIL_BLOCK_ALERT_TRIGGERS is enabled")
        return {"status": "ignored", "reason": "alert-triggered runs are disabled"}
    payload = await request.json()
    if not payload.get("alerts"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload has no alerts",
        )
    event = FaultEvent.model_validate(payload)
    model_name = model or os.environ.get("LLM_MODEL_NAME", "unknown")
    run_id, _, _ = build_run_id(scenario, model_name, seed=seed)
    task = asyncio.create_task(
        run_orchestration(
            event,
            kubectl_mcp=request.app.state.kubectl_mcp,
            flux_mcp=request.app.state.flux_mcp,
            nixos_mcp=request.app.state.nixos_mcp,
            git_mcp=request.app.state.git_mcp,
            scenario=scenario,
            seed=seed,
            model_name=model_name,
            run_id=run_id,
        )
    )
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)
    task.add_done_callback(lambda t: log_task_exception(t, log))
    return {"run_id": run_id}
