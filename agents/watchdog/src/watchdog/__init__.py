"""Vigil watchdog agent package."""

from .agent import (
    HEALTHY_STREAK_K,
    POLL_INTERVAL_S,
    WATCHDOG_POLL_INTERVAL_S,
    WATCHDOG_WINDOW_S,
    WINDOW_S,
    capture_health_snapshot,
    is_workload_healthy,
    run_watchdog,
)
from .models import HealthSnapshot, WatchdogDeps, WatchdogResult

__all__ = [
    "HEALTHY_STREAK_K",
    "POLL_INTERVAL_S",
    "WATCHDOG_POLL_INTERVAL_S",
    "WATCHDOG_WINDOW_S",
    "WINDOW_S",
    "HealthSnapshot",
    "WatchdogDeps",
    "WatchdogResult",
    "capture_health_snapshot",
    "is_workload_healthy",
    "run_watchdog",
]
