"""Shared pytest fixtures for agent tests. Mock MCP clients avoid live cluster deps."""

from unittest.mock import AsyncMock

import pytest
from orchestrator.models import FaultEvent


@pytest.fixture
def sample_fault_event() -> FaultEvent:
    """K8s-1 wrong-image-tag Alertmanager payload."""
    return FaultEvent(
        receiver="vigil-webhook",
        status="firing",
        alerts=[
            {
                "status": "firing",
                "labels": {
                    "alertname": "KubePodImagePullBackOff",
                    "namespace": "default",
                    "deployment": "vigil-app",
                    "pod": "vigil-app-7d9f-xxxx",
                },
                "annotations": {
                    "summary": "Pod cannot pull image",
                    "description": "image vigil-app:bad-tag-v9 not found",
                },
                "startsAt": "2026-04-18T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
            }
        ],
        groupLabels={"alertname": "KubePodImagePullBackOff"},
        commonLabels={"namespace": "default", "deployment": "vigil-app"},
        commonAnnotations={"summary": "Pod cannot pull image"},
        externalURL="http://alertmanager.monitoring:9093",
        version="4",
        groupKey='{}:{alertname="KubePodImagePullBackOff"}',
    )


@pytest.fixture
def mock_kubectl_mcp() -> AsyncMock:
    m = AsyncMock()
    m.call_tool = AsyncMock(
        return_value={"content": "pod/vigil-app-xxx ImagePullBackOff"}
    )
    return m


@pytest.fixture
def mock_flux_mcp() -> AsyncMock:
    m = AsyncMock()
    m.call_tool = AsyncMock(return_value={"content": "kustomization ok"})
    m.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    return m


@pytest.fixture
def mock_ssh_mcp() -> AsyncMock:
    m = AsyncMock()
    m.call_tool = AsyncMock(return_value={"content": "ssh ok"})
    return m


@pytest.fixture
def mock_nixos_mcp() -> AsyncMock:
    m = AsyncMock()
    m.call_tool = AsyncMock(return_value={"content": "nixos rebuild ok"})
    return m


@pytest.fixture
def mock_git_mcp() -> AsyncMock:
    m = AsyncMock()
    m.call_tool = AsyncMock(return_value={"content": "ok"})
    m.direct_call_tool = AsyncMock(return_value={"content": "ok"})
    return m
