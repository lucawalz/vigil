from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from common.constants import (
    GATE_REVERT_CALL_TIMEOUT_S,
    GATE_WAIT_TIMEOUT_MAX_S,
    GATE_WAIT_TIMEOUT_MIN_S,
    GATE_WAIT_TIMEOUT_S,
    GIT_MCP_READ_TIMEOUT_S,
    LLM_MAX_RETRIES,
    LLM_REQUEST_TIMEOUT_S,
    MCP_CALL_TIMEOUT_S,
    POLLER_UNHEALTHY_AFTER,
    ROLLBACK_TIMEOUT_S,
    ROLLBACK_VERIFY_WINDOW_S,
    SHUTDOWN_DRAIN_S,
    SHUTDOWN_STOP_MARGIN_S,
    SHUTDOWN_STOP_TIMEOUT_S,
)
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_ai.mcp import MCPServerStdio
from watchdog.agent import WATCHDOG_WINDOW_S

from .agent import (
    DIAGNOSIS_TIMEOUT_S,
    ORCHESTRATOR_RUN_TIMEOUT_S,
    REMEDIATION_TIMEOUT_S,
    active_run_count,
    build_run_id,
    drain_runs,
    run_orchestration,
    track_run,
)
from .models import FaultEvent, eval_target_from_env
from .poller import prometheus_poller

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


def _check_gate_wait_budget() -> None:
    if not GATE_WAIT_TIMEOUT_MIN_S <= GATE_WAIT_TIMEOUT_S <= GATE_WAIT_TIMEOUT_MAX_S:
        raise ValueError(
            f"GATE_WAIT_TIMEOUT_S must be between {GATE_WAIT_TIMEOUT_MIN_S} and "
            f"{GATE_WAIT_TIMEOUT_MAX_S} seconds, got {GATE_WAIT_TIMEOUT_S}"
        )
    gate_wait = ("GATE_WAIT_TIMEOUT_S", GATE_WAIT_TIMEOUT_S)
    read = ("GIT_MCP_READ_TIMEOUT_S", GIT_MCP_READ_TIMEOUT_S)
    llm_retry_s = (1 + LLM_MAX_RETRIES) * LLM_REQUEST_TIMEOUT_S
    llm_retry = ("(1 + LLM_MAX_RETRIES) * LLM_REQUEST_TIMEOUT_S", llm_retry_s)
    revert_call = ("GATE_REVERT_CALL_TIMEOUT_S", GATE_REVERT_CALL_TIMEOUT_S)
    remediation = ("REMEDIATION_TIMEOUT_S", REMEDIATION_TIMEOUT_S)
    attempt = (
        "DIAGNOSIS_TIMEOUT_S + REMEDIATION_TIMEOUT_S + GIT_MCP_READ_TIMEOUT_S + "
        "2 * MCP_CALL_TIMEOUT_S + WATCHDOG_WINDOW_S",
        DIAGNOSIS_TIMEOUT_S
        + REMEDIATION_TIMEOUT_S
        + GIT_MCP_READ_TIMEOUT_S
        + 2 * MCP_CALL_TIMEOUT_S
        + WATCHDOG_WINDOW_S,
    )
    run = ("ORCHESTRATOR_RUN_TIMEOUT_S", ORCHESTRATOR_RUN_TIMEOUT_S)
    for (shorter, shorter_s), (longer, longer_s) in (
        (gate_wait, read),
        (read, revert_call),
        (llm_retry, remediation),
        (attempt, run),
    ):
        if shorter_s >= longer_s:
            raise ValueError(
                f"{shorter} ({shorter_s}s) must be below {longer} ({longer_s}s)"
            )
    rollback_s = (
        GATE_REVERT_CALL_TIMEOUT_S + MCP_CALL_TIMEOUT_S + ROLLBACK_VERIFY_WINDOW_S
    )
    if rollback_s > ROLLBACK_TIMEOUT_S:
        raise ValueError(
            "GATE_REVERT_CALL_TIMEOUT_S + MCP_CALL_TIMEOUT_S + "
            f"ROLLBACK_VERIFY_WINDOW_S ({rollback_s}s) must not exceed "
            f"ROLLBACK_TIMEOUT_S ({ROLLBACK_TIMEOUT_S}s)"
        )
    stop_s = SHUTDOWN_DRAIN_S + SHUTDOWN_STOP_MARGIN_S
    if stop_s > SHUTDOWN_STOP_TIMEOUT_S:
        raise ValueError(
            f"SHUTDOWN_DRAIN_S + SHUTDOWN_STOP_MARGIN_S ({stop_s}s) must not exceed "
            f"SHUTDOWN_STOP_TIMEOUT_S ({SHUTDOWN_STOP_TIMEOUT_S}s)"
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    eval_target_from_env()
    _check_gate_wait_budget()
    _configure_logging()
    cmds = _mcp_commands()
    # MCPServerStdio defaults env=None which gives child processes an empty
    # environment, breaking KUBECONFIG, PATH, etc.
    env = os.environ.copy()
    git_env = {**env, "GATE_WAIT_TIMEOUT_S": str(GATE_WAIT_TIMEOUT_S)}

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
            command=git_argv[0],
            args=git_argv[1:],
            env=git_env,
            max_retries=3,
            read_timeout=GIT_MCP_READ_TIMEOUT_S,
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
        log.info("draining %d active runs", active_run_count())
        await drain_runs()
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
    track_run(task)
    return {"run_id": run_id}
