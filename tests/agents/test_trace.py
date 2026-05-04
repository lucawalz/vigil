"""Unit tests for vigil.agent.trace — upgraded log_messages() behavior."""

from __future__ import annotations

import logging

from common.trace import _TRUNC, _t, log_messages
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
)


def _tool_call_msg(tool_name: str, args: str) -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name=tool_name, args=args, tool_call_id="tc1")]
    )


def _text_msg(content: str) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=content)])


def _tool_return_msg(tool_name: str, content: str) -> ModelRequest:
    return ModelRequest(
        parts=[ToolReturnPart(tool_name=tool_name, content=content, tool_call_id="tc1")]
    )


def test_trunc_value_is_1000():
    assert _TRUNC == 1000


def test_trunc_helper_cuts_at_1000():
    long = "x" * 1001
    result = _t(long)
    assert len(result) == 1001  # 1000 chars + "…"
    assert result.endswith("…")


def test_trunc_helper_passthrough_short():
    short = "abc"
    assert _t(short) == "abc"


def test_tool_call_emits_info_with_iter_prefix(caplog):
    msgs = [_tool_call_msg("kubectl_get_pods", '{"namespace":"default"}')]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("k8s-1_1_qwen_abc", "diagnosis", msgs)
    assert any(
        "iter" in r.message and "kubectl_get_pods" in r.message for r in caplog.records
    )
    kp_recs = [r for r in caplog.records if "kubectl_get_pods" in r.message]
    assert all(r.levelno == logging.INFO for r in kp_recs)


def test_text_part_emits_info(caplog):
    msgs = [_text_msg("CrashLoopBackOff detected — recommend rollout_undo")]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("k8s-1_1_qwen_abc", "diagnosis", msgs)
    assert any("model:" in r.message for r in caplog.records)
    assert all(
        r.levelno == logging.INFO for r in caplog.records if "model:" in r.message
    )


def test_tool_return_emits_info(caplog):
    msgs = [_tool_return_msg("kubectl_get_pods", "pod/nginx-xxx Running")]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("k8s-1_1_qwen_abc", "diagnosis", msgs)
    assert any("←" in r.message for r in caplog.records)
    assert all(r.levelno == logging.INFO for r in caplog.records if "←" in r.message)


def test_iter_counter_increments_per_tool_call(caplog):
    msgs = [
        _tool_call_msg("tool_a", "{}"),
        _text_msg("thinking..."),
        _tool_call_msg("tool_b", "{}"),
    ]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("run1", "diagnosis", msgs)
    messages = [r.message for r in caplog.records if "iter" in r.message]
    # First tool call should be iter 1, second iter 2
    assert any("iter 1" in m for m in messages)
    assert any("iter 2" in m for m in messages)


def test_iter_counter_resets_between_calls(caplog):
    msgs = [_tool_call_msg("tool_a", "{}"), _tool_call_msg("tool_b", "{}")]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("run1", "diagnosis", msgs)
        log_messages("run1", "remediation", msgs)
    diag = [
        r.message
        for r in caplog.records
        if "diagnosis" in r.message and "iter" in r.message
    ]
    rem = [
        r.message
        for r in caplog.records
        if "remediation" in r.message and "iter" in r.message
    ]
    assert any("iter 1" in m for m in diag)
    assert any("iter 1" in m for m in rem)


def test_log_line_format_includes_run_id_and_phase(caplog):
    msgs = [_tool_call_msg("tool_a", "{}")]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("myrun_abc", "remediation", msgs)
    assert any(
        "myrun_abc" in r.message and "remediation" in r.message for r in caplog.records
    )


def test_empty_text_part_not_logged(caplog):
    msgs = [_text_msg("   ")]
    with caplog.at_level(logging.INFO, logger="vigil.agent.trace"):
        log_messages("run1", "diagnosis", msgs)
    assert not any("model:" in r.message for r in caplog.records)
