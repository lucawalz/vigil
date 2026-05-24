from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pydantic_ai.messages import (
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)

_log = logging.getLogger("vigil.agent.trace")
_TRUNC = 1000


def _t(s: str) -> str:
    return s[:_TRUNC] + "…" if len(s) > _TRUNC else s


def log_messages(run_id: str, phase: str, messages: list[ModelMessage]) -> None:
    _iter = 0
    for msg in messages:
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    _iter += 1
                    _log.info(
                        "[%s | %s | iter %d] → %s(%s)",
                        run_id,
                        phase,
                        _iter,
                        part.tool_name,
                        _t(str(part.args)),
                    )
                elif isinstance(part, TextPart) and part.content.strip():
                    _log.info(
                        "[%s | %s | iter %d] model: %s",
                        run_id,
                        phase,
                        _iter,
                        _t(part.content),
                    )
        elif isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, ToolReturnPart):
                    _log.info(
                        "[%s | %s | iter %d] ← %s: %s",
                        run_id,
                        phase,
                        _iter,
                        part.tool_name,
                        _t(str(part.content)),
                    )


def write_trace(
    run_id: str, phase: str, messages: list[ModelMessage], partial: bool = False
) -> None:
    runs_dir = os.environ.get("EVAL_RUNS_DIR", "eval/runs")
    os.makedirs(runs_dir, exist_ok=True)
    path = Path(runs_dir) / f"{run_id}_trace.jsonl"
    serialized = ModelMessagesTypeAdapter.dump_python(messages, mode="json")
    with path.open("a") as f:
        for item in serialized:
            f.write(json.dumps({"phase": phase, "partial": partial, **item}) + "\n")
