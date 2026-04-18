"""Vigil watchdog agent package."""

from .agent import (
    POLL_INTERVAL_S,
    WATCHDOG_POLL_INTERVAL_S,
    WATCHDOG_WINDOW_S,
    WINDOW_S,
    capture_health_snapshot,
    run_watchdog,
)
from .models import HealthSnapshot, WatchdogDeps, WatchdogResult

__all__ = [
    "POLL_INTERVAL_S",
    "WATCHDOG_POLL_INTERVAL_S",
    "WATCHDOG_WINDOW_S",
    "WINDOW_S",
    "HealthSnapshot",
    "WatchdogDeps",
    "WatchdogResult",
    "capture_health_snapshot",
    "run_watchdog",
]
