from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Annotated, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_ai.mcp import MCPServerStdio

from .agent import build_run_id, run_orchestration
from .models import FaultEvent

log = logging.getLogger("vigil.orchestrator")


def _mcp_commands() -> dict[str, list[str]]:
    return {
        "kubectl": os.environ.get("KUBECTL_MCP_CMD", "kubectl-mcp").split(),
        "flux": os.environ.get("FLUX_MCP_CMD", "flux-mcp").split(),
        "ssh": os.environ.get("SSH_MCP_CMD", "ssh-mcp").split(),
        "nixos": os.environ.get("NIXOS_MCP_CMD", "nixos-mcp").split(),
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    cmds = _mcp_commands()
    # MCPServerStdio defaults env=None which gives child processes an empty
    # environment, breaking KUBECONFIG, PATH, etc.
    env = os.environ.copy()

    kubectl_argv = cmds["kubectl"]
    flux_argv = cmds["flux"]
    ssh_argv = cmds["ssh"]
    nixos_argv = cmds["nixos"]

    async with (
        MCPServerStdio(
            command=kubectl_argv[0], args=kubectl_argv[1:], env=env, max_retries=3
        ) as kubectl_mcp,
        MCPServerStdio(command=flux_argv[0], args=flux_argv[1:], env=env) as flux_mcp,
        MCPServerStdio(command=ssh_argv[0], args=ssh_argv[1:], env=env) as ssh_mcp,
        MCPServerStdio(
            command=nixos_argv[0], args=nixos_argv[1:], env=env
        ) as nixos_mcp,
    ):
        app.state.kubectl_mcp = kubectl_mcp
        app.state.flux_mcp = flux_mcp
        app.state.ssh_mcp = ssh_mcp
        app.state.nixos_mcp = nixos_mcp
        log.info("MCP servers booted: kubectl, flux, ssh, nixos")
        yield
        log.info("MCP servers shutting down")


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
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook", dependencies=[Depends(_check_auth)])
async def webhook(
    request: Request,
    scenario: str = "k8s-1",
    seed: int | None = None,
) -> dict[str, str]:
    payload = await request.json()
    if not payload.get("alerts"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload has no alerts",
        )
    event = FaultEvent.model_validate(payload)
    model_name = os.environ.get("LLM_MODEL_NAME", "unknown")
    run_id, _, _ = build_run_id(scenario, model_name, seed=seed)
    asyncio.create_task(
        run_orchestration(
            event,
            kubectl_mcp=request.app.state.kubectl_mcp,
            flux_mcp=request.app.state.flux_mcp,
            ssh_mcp=request.app.state.ssh_mcp,
            nixos_mcp=request.app.state.nixos_mcp,
            scenario=scenario,
            seed=seed,
        )
    )
    return {"run_id": run_id}
