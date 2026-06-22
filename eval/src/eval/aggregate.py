from __future__ import annotations

import json
import logging
import statistics
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_GROUP_LABELS: dict[str, str] = {
    "k8s": "Kubernetes Layer",
    "os": "OS / NixOS Layer",
    "cross": "Cross-Layer",
    "misc": "Infrastructure / Misc",
}

_GROUP_ORDER = ["k8s", "os", "cross", "misc"]

_OUTCOME_BUCKET: dict[str, str] = {
    "success": "passed",
    "rollback_succeeded": "passed",
    "flux_degraded": "agent-failed",
    "diagnosis_inconsistent": "agent-failed",
    "diagnosis_timeout": "agent-failed",
    "budget_exhausted": "agent-failed",
    "rollback_failed": "agent-failed",
    "quota_exhausted": "agent-failed",
    "commit_generation_failed": "agent-failed",
    "baseline_degraded": "infra-error",
    "abort": "infra-error",
    "setup_error": "infra-error",
    "inject_did_not_break": "infra-error",
    "gate_failed": "gate-uncertain",
    "awaiting_human_review": "awaiting-review",
}

_UNKNOWN_OUTCOME_BUCKET = "infra-error"

_OUTCOME_TOKEN: dict[str, str] = {
    "success": "OK",
    "rollback_succeeded": "RB",
    "escalated": "ESC",
    "abort": "TO",
    "setup_error": "SE",
}

_UNKNOWN_OUTCOME_TOKEN = "??"

_UNCREDITED_TOKEN = "KO"
_CREDIT_BEARING_OUTCOMES = frozenset({"success", "rollback_succeeded"})

_OUTCOME_TOKEN_LEGEND = (
    "legend: OK success  RB rollback  ESC escalated  TO abort/timeout  "
    "SE setup_error  KO healthy but fix not credited"
)

_CLOSED_GATE = "closed"

_AGENT_ATTRIBUTABLE_ABORT_PREFIXES = (
    "diagnosis_request_limit_",
    "retry_exhausted:",
)
_AGENT_ATTRIBUTABLE_ABORT_REASONS = frozenset({"iteration_limit"})


def _bucket_outcome(literal: str) -> str:
    bucket = _OUTCOME_BUCKET.get(literal)
    if bucket is None:
        log.warning(
            "unmapped outcome %r; bucketing as %s", literal, _UNKNOWN_OUTCOME_BUCKET
        )
        return _UNKNOWN_OUTCOME_BUCKET
    return bucket


def _outcome_token(literal: str) -> str:
    return _OUTCOME_TOKEN.get(literal, _UNKNOWN_OUTCOME_TOKEN)


def _seed_token(outcome: str, success_rate: Any) -> str:
    if outcome in _CREDIT_BEARING_OUTCOMES and not success_rate:
        return _UNCREDITED_TOKEN
    return _outcome_token(outcome)


def _seed_sort_key(run: dict) -> str:
    return str(run.get("seed", ""))


def _sort_runs_by_seed(runs: list[dict]) -> list[dict]:
    seeds = [r.get("seed", "") for r in runs]
    try:
        int_seeds = [int(s) for s in seeds]
    except (TypeError, ValueError):
        return sorted(runs, key=_seed_sort_key)
    return [run for _, run in sorted(zip(int_seeds, runs), key=lambda pair: pair[0])]


def _bucket_gate_failed(record: dict) -> str:
    if (
        record.get("gate_status") == _CLOSED_GATE
        and record.get("merge_commit_sha") is None
    ):
        return "agent-failed"
    return "gate-uncertain"


def _is_agent_attributable_abort(reason: str) -> bool:
    return reason in _AGENT_ATTRIBUTABLE_ABORT_REASONS or reason.startswith(
        _AGENT_ATTRIBUTABLE_ABORT_PREFIXES
    )


def _count_buckets(records: Any, n_planned: int = 0) -> dict[str, int]:
    counts: dict[str, int] = {
        "passed": 0,
        "agent-failed": 0,
        "infra-error": 0,
        "gate-uncertain": 0,
        "awaiting-review": 0,
        "not-run": 0,
    }
    n_seen = 0
    for r in records:
        if r is None:
            continue
        n_seen += 1
        outcome = r.get("outcome", "")
        success_rate = r.get("success_rate")
        if outcome == "success" and not success_rate:
            counts["agent-failed"] += 1
        elif outcome == "escalated":
            counts["passed" if success_rate else "agent-failed"] += 1
        elif outcome == "abort" and _is_agent_attributable_abort(
            str(r.get("setup_error") or "")
        ):
            counts["agent-failed"] += 1
        elif outcome == "gate_failed":
            counts[_bucket_gate_failed(r)] += 1
        else:
            counts[_bucket_outcome(outcome)] += 1
    counts["not-run"] = max(0, n_planned - n_seen)
    return counts


def _scenario_group(scenario_id: str) -> str:
    for prefix in ("k8s-", "os-", "cross-"):
        if scenario_id.startswith(prefix):
            return prefix.rstrip("-")
    return "misc"


def _load_records(runs_dir: Path, index_path: Path) -> list[dict]:
    records: list[dict] = []
    if not index_path.exists():
        return records
    seen: set[str] = set()
    with index_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            idx_rec = json.loads(line)
            run_id = idx_rec["run_id"]
            if run_id in seen:
                continue
            seen.add(run_id)
            run_file = runs_dir / f"{run_id}.json"
            if run_file.exists():
                records.append(json.loads(run_file.read_text()))
            else:
                log.warning("run JSON missing for %s; skipping", run_id)
    return records


def _mean_std(vals: list[float]) -> tuple[float | None, float | None]:
    if not vals:
        return None, None
    m = statistics.mean(vals)
    s = statistics.stdev(vals) if len(vals) > 1 else None
    return m, s


def _layer_for_scenario(scenarios_dir: Path, scenario_id: str) -> str | None:
    p = scenarios_dir / scenario_id / "scenario.yaml"
    if not p.exists():
        return None
    with p.open() as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("layer")


def _expected_action_for_scenario(scenarios_dir: Path, scenario_id: str) -> str | None:
    p = scenarios_dir / scenario_id / "scenario.yaml"
    if not p.exists():
        return None
    with p.open() as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("expected_action")


def _expected_outcome_for_scenario(scenarios_dir: Path, scenario_id: str) -> str | None:
    p = scenarios_dir / scenario_id / "scenario.yaml"
    if not p.exists():
        return None
    with p.open() as fh:
        data = yaml.safe_load(fh) or {}
    return data.get("expected_outcome")


def _correct_escalation_success(records: list[dict], scenarios_dir: Path) -> None:
    """Score agent-driven escalations against expected_action from scenario.yaml."""
    for r in records:
        if (
            r.get("outcome") == "escalated"
            and r.get("success_rate") is None
            and not r.get("setup_error")
        ):
            expected = _expected_action_for_scenario(
                scenarios_dir, r.get("scenario", "")
            )
            r["success_rate"] = expected == "escalate" and (
                r.get("diagnosis_accuracy") is True
            )


def _correct_outcome_success(records: list[dict], scenarios_dir: Path) -> None:
    """Score runs whose outcome matches the scenario's expected_outcome as success."""
    for r in records:
        if r.get("setup_error"):
            continue
        expected = _expected_outcome_for_scenario(scenarios_dir, r.get("scenario", ""))
        if (
            expected
            and r.get("outcome") == expected
            and not r.get("forbidden_action_violations")
        ):
            r["success_rate"] = True


def _is_genuine_infra_abort(run: dict) -> bool:
    return run.get("outcome") == "abort" and not _is_agent_attributable_abort(
        str(run.get("setup_error") or "")
    )


def _summarize_model(runs: list[dict]) -> dict:
    successes = [r for r in runs if r.get("success_rate")]
    attempts = [r for r in runs if not _is_genuine_infra_abort(r)]
    non_aborts = [r for r in runs if r.get("outcome") != "abort"]
    mttrs = [
        r["MTTR_s"]
        for r in runs
        if isinstance(r.get("MTTR_s"), (int, float)) and r.get("success_rate")
    ]
    diag_acc = [r for r in runs if r.get("diagnosis_accuracy") is not None]
    diag_correct = [r for r in diag_acc if r["diagnosis_accuracy"]]
    dest = [r for r in runs if r.get("destructive_repair")]
    rollbacks = [r for r in runs if r.get("rollback_triggered")]
    rollback_successes = [r for r in rollbacks if r.get("rollback_success")]
    mean_mttr, std_mttr = _mean_std(mttrs)
    n_attempts = len(attempts)
    return {
        "n_runs": len(runs),
        "n_attempts": n_attempts,
        "success_rate": len(successes) / len(runs) if runs else 0.0,
        "success_rate_given_attempt": (
            len(successes) / n_attempts if n_attempts else None
        ),
        "mean_MTTR_s": mean_mttr,
        "std_MTTR_s": std_mttr,
        "diagnosis_accuracy": (len(diag_correct) / len(diag_acc) if diag_acc else None),
        "diag_n": len(diag_acc),
        "destructive_repair_rate": len(dest) / len(runs) if runs else 0.0,
        "rollback_triggered_rate": len(rollbacks) / len(runs) if runs else 0.0,
        "rollback_success_rate": (
            len(rollback_successes) / len(rollbacks) if rollbacks else None
        ),
        "n_eligible": n_attempts,
        "mean_input_tokens": _mean_std(
            [r.get("total_input_tokens", 0) for r in non_aborts]
        )[0],
        "mean_output_tokens": _mean_std(
            [r.get("total_output_tokens", 0) for r in non_aborts]
        )[0],
        "mean_tool_calls": _mean_std(
            [r.get("total_tool_calls", 0) for r in non_aborts]
        )[0],
        "mean_iteration_count": _mean_std(
            [r.get("iteration_count", 0) for r in non_aborts]
        )[0],
    }


def _summarize_scenario(runs: list[dict]) -> dict:
    ordered = _sort_runs_by_seed(runs)
    successes = [r for r in ordered if r.get("success_rate")]
    mttrs = [
        r["MTTR_s"]
        for r in ordered
        if isinstance(r.get("MTTR_s"), (int, float)) and r.get("success_rate")
    ]
    mean_mttr, std_mttr = _mean_std(mttrs)
    diag_scored = [r for r in ordered if r.get("diagnosis_accuracy") is not None]
    diag_correct = [r for r in diag_scored if r["diagnosis_accuracy"] is True]
    executed = [r for r in ordered if (r.get("iteration_count") or 0) > 0]
    mean_iters = _mean_std([r["iteration_count"] for r in executed])[0]
    mean_tools = _mean_std([r.get("total_tool_calls", 0) for r in executed])[0]
    representative = ordered[0] if ordered else {}
    return {
        "n_runs": len(ordered),
        "outcome": representative.get("outcome"),
        "setup_error": representative.get("setup_error"),
        "forbidden_action_violations": representative.get(
            "forbidden_action_violations"
        ),
        "per_seed": [
            {
                "seed": r.get("seed"),
                "outcome": r.get("outcome", ""),
                "success_rate": r.get("success_rate"),
            }
            for r in ordered
        ],
        "passed": len(successes),
        "n_seeds": len(ordered),
        "diag_correct": len(diag_correct),
        "diag_total": len(diag_scored),
        "success_rate": len(successes) / len(ordered) if ordered else 0.0,
        "mean_MTTR_s": mean_mttr,
        "std_MTTR_s": std_mttr,
        "mean_iteration_count": mean_iters,
        "mean_tool_calls": mean_tools,
    }


def _summarize_escalation(runs: list[dict], layer: str | None) -> dict:
    if layer != "os":
        return {"layer": layer, "accuracy": None}
    scored = [r for r in runs if r.get("diagnosis_accuracy") is not None]
    correct = [r for r in scored if r["diagnosis_accuracy"]]
    per_model: dict[str, dict] = {}
    for r in scored:
        m = r["model"]
        slot = per_model.setdefault(m, {"correct": 0, "total": 0})
        slot["total"] += 1
        if r["diagnosis_accuracy"]:
            slot["correct"] += 1
    return {
        "layer": layer,
        "correct": len(correct),
        "total": len(scored),
        "accuracy": (len(correct) / len(scored)) if scored else None,
        "per_model": per_model,
    }


def _planned_run_count(
    planned_scenarios: list[str],
    by_scenario: dict,
    n_records: int,
    seed_count: int | None,
) -> int:
    if not planned_scenarios:
        return n_records
    seeds_per_scenario = seed_count if seed_count else _seed_count(by_scenario)
    return len(planned_scenarios) * seeds_per_scenario


def aggregate_runs(
    runs_dir: Path,
    index_path: Path,
    scenarios_dir: Path,
    seed_count: int | None = None,
) -> dict[str, Any]:
    """Compute per-model and per-scenario metric tables plus escalation accuracy."""
    records = _load_records(runs_dir, index_path)
    planned_scenarios: list[str] = (
        sorted(p.name for p in scenarios_dir.iterdir() if p.is_dir())
        if scenarios_dir.is_dir()
        else []
    )
    _correct_escalation_success(records, scenarios_dir)
    _correct_outcome_success(records, scenarios_dir)
    if not records:
        return {
            "by_model": {},
            "by_scenario": {},
            "escalation": {},
            "totals": {"n": 0, "n_models": 0, "n_scenarios": 0},
            "planned_scenarios": planned_scenarios,
        }

    by_model: dict[str, list[dict]] = {}
    by_scenario: dict[str, list[dict]] = {}
    for r in records:
        by_model.setdefault(r["model"], []).append(r)
        by_scenario.setdefault(r["scenario"], []).append(r)

    model_summary = {model: _summarize_model(runs) for model, runs in by_model.items()}

    scenario_summary: dict[str, dict] = {}
    escalation: dict[str, dict] = {}
    for scenario, runs in by_scenario.items():
        scenario_summary[scenario] = _summarize_scenario(runs)
        layer = _layer_for_scenario(scenarios_dir, scenario)
        escalation[scenario] = _summarize_escalation(runs, layer)

    n_planned_runs = _planned_run_count(
        planned_scenarios, scenario_summary, len(records), seed_count
    )
    run_buckets = _count_buckets(records, n_planned=n_planned_runs)
    scenarios_passing_all = sum(
        1
        for row in scenario_summary.values()
        if row.get("n_seeds", 0) > 0 and row["passed"] == row["n_seeds"]
    )

    return {
        "by_model": model_summary,
        "by_scenario": scenario_summary,
        "escalation": escalation,
        "run_buckets": run_buckets,
        "n_runs": len(records),
        "n_planned_runs": n_planned_runs,
        "scenarios_passing_all_seeds": scenarios_passing_all,
        "totals": {
            "n": len(records),
            "n_models": len(by_model),
            "n_scenarios": len(by_scenario),
        },
        "planned_scenarios": planned_scenarios,
    }


def _ordered_scenario_keys(by_scenario: dict, planned: list[str]) -> list[str]:
    scenario_keys = planned if planned else sorted(by_scenario)
    ordered: list[str] = []
    for group in _GROUP_ORDER:
        ordered.extend(s for s in scenario_keys if _scenario_group(s) == group)
    for s in scenario_keys:
        if s not in ordered:
            ordered.append(s)
    return ordered


def _seed_count(by_scenario: dict) -> int:
    counts = [row.get("n_seeds", row.get("n_runs", 0)) for row in by_scenario.values()]
    return max(counts) if counts else 1


def _mttr_cell(row: dict) -> str:
    mean = row.get("mean_MTTR_s")
    if mean is None:
        return "—"
    std = row.get("std_MTTR_s")
    if std is None:
        return f"{mean:.0f}"
    return f"{mean:.0f} ± {std:.0f}"


def _diag_cell(row: dict) -> str:
    total = row.get("diag_total", 0)
    if not total:
        return "—"
    return f"{row.get('diag_correct', 0)}/{total}"


def _per_seed_strip(row: dict, n_seeds: int) -> str:
    tokens = [
        _seed_token(s.get("outcome", ""), s.get("success_rate"))
        for s in row.get("per_seed", [])
    ]
    tokens += ["—"] * (n_seeds - len(tokens))
    return " ".join(tokens)


def _scenario_table_lines(
    by_scenario: dict, planned: list[str], n_seeds: int
) -> list[str]:
    seed_header = " ".join(f"s{i}" for i in range(1, n_seeds + 1))
    lines = [
        f"| scenario | pass | {seed_header} | MTTR mean±std | diag | iters | tools |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    ordered = _ordered_scenario_keys(by_scenario, planned)
    empty_strip = " ".join("—" for _ in range(n_seeds))
    for s in ordered:
        row = by_scenario.get(s)
        if row is None:
            lines.append(f"| {s} | no data | {empty_strip} | — | — | — | — |")
            continue
        lines.append(
            f"| {s} | {row.get('passed', 0)}/{row.get('n_seeds', 0)}"
            f" | {_per_seed_strip(row, n_seeds)}"
            f" | {_mttr_cell(row)} | {_diag_cell(row)}"
            f" | {_fmt_mean(row.get('mean_iteration_count'))}"
            f" | {_fmt_mean(row.get('mean_tool_calls'))} |"
        )
    return lines


def _grouped_scenario_table_lines(by_scenario: dict, planned: list[str]) -> list[str]:
    n_seeds = _seed_count(by_scenario)
    ordered = _ordered_scenario_keys(by_scenario, planned)
    lines: list[str] = []
    for group in _GROUP_ORDER:
        members = [s for s in ordered if _scenario_group(s) == group]
        if not members:
            continue
        subset = {s: by_scenario.get(s) for s in members}
        lines.append(f"#### {_GROUP_LABELS[group]}")
        lines.append("")
        lines += _scenario_table_lines(subset, members, n_seeds)
        lines.append("")
        lines.append(_OUTCOME_TOKEN_LEGEND)
        lines.append("")
    return lines


def _bucket_rollup_lines(
    counts: dict[str, int],
    n_runs: int,
    scenarios_passing_all: int,
    n_scenarios: int,
) -> list[str]:
    return [
        f"{counts['passed']}/{n_runs} runs passed, "
        f"{counts['agent-failed']} agent-failed, "
        f"{counts['infra-error']} infra-error, "
        f"{counts['gate-uncertain']} gate-uncertain, "
        f"{counts['awaiting-review']} awaiting-review, "
        f"{counts['not-run']} not-run",
        f"{scenarios_passing_all}/{n_scenarios} scenarios passed all seeds",
    ]


def write_report(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    lines: list[str] = []
    lines.append("# Eval Campaign Aggregation Report")
    lines.append("")
    lines.append(
        f"Total runs: {summary['totals']['n']} across "
        f"{summary['totals']['n_models']} models "
        f"and {summary['totals']['n_scenarios']} scenarios."
    )
    lines.append("")

    lines.append("## Per-Model Summary")
    lines.append("")
    lines.append(
        "| Model | N | Success Rate | Mean MTTR (s) | Std MTTR (s) | "
        "Diag. Accuracy | Destructive % | Rollback % | Rollback Success % | "
        "Mean In/Out Tokens | Mean Tool Calls | Mean Iterations |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    for m, row in summary["by_model"].items():
        lines.append(
            f"| {m} | {row['n_runs']} | "
            f"{row['success_rate']:.2f} | "
            f"{_fmt(row['mean_MTTR_s'])} | {_fmt(row['std_MTTR_s'])} | "
            f"{_fmt_diag(row['diagnosis_accuracy'], row.get('diag_n'))} | "
            f"{row['destructive_repair_rate']:.2f} | "
            f"{row['rollback_triggered_rate']:.2f} | "
            f"{_fmt(row.get('rollback_success_rate'))} | "
            f"{_fmt(row['mean_input_tokens'])}/{_fmt(row['mean_output_tokens'])} | "
            f"{_fmt(row['mean_tool_calls'])} | "
            f"{_fmt(row['mean_iteration_count'])} |"
        )
    lines.append("")

    lines.append("## Per-Scenario Summary")
    lines.append("")
    by_scenario = summary["by_scenario"]
    planned: list[str] = summary.get("planned_scenarios") or []
    counts = summary.get("run_buckets") or _count_buckets(by_scenario.values())
    lines += _bucket_rollup_lines(
        counts,
        summary.get("n_runs", len(by_scenario)),
        summary.get("scenarios_passing_all_seeds", 0),
        summary["totals"]["n_scenarios"],
    )
    lines.append("")
    lines += _grouped_scenario_table_lines(by_scenario, planned)

    lines.append("## Cross-Layer Escalation Accuracy")
    lines.append("")
    lines.append("| Scenario | Layer | Correct/Total | Accuracy |")
    lines.append("|---|---|---:|---:|")
    for s, row in summary["escalation"].items():
        if row.get("accuracy") is None:
            lines.append(f"| {s} | {row.get('layer', '—')} | — | N/A |")
        else:
            lines.append(
                f"| {s} | {row['layer']} | {row['correct']}/{row['total']} | "
                f"{row['accuracy']:.2f} |"
            )
    lines.append("")

    lines.append("---")
    lines.append("")
    seed_counts = [row["n_runs"] for row in summary["by_scenario"].values()]
    max_n = max(seed_counts) if seed_counts else 0
    if max_n <= 1:
        footer = "_Single-seed campaign - std values omitted._"
    else:
        footer = (
            f"_Note: std values computed from {max_n} seeds per cell; "
            "treat as directional only._"
        )
    lines.append(footer)

    (output_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def write_step_summary(
    runs_dir: Path,
    index_path: Path,
    output_dir: Path,
    scenarios_dir: Path | None = None,
    seed_count: int | None = None,
) -> None:
    records = _load_records(runs_dir, index_path)
    if scenarios_dir is not None:
        _correct_escalation_success(records, scenarios_dir)
        _correct_outcome_success(records, scenarios_dir)
    if not records:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "step_summary.md").write_text("No run data available.\n")
        return

    by_scenario_runs: dict[str, list[dict]] = {}
    for r in records:
        by_scenario_runs.setdefault(r["scenario"], []).append(r)
    by_scenario = {
        sid: _summarize_scenario(runs) for sid, runs in by_scenario_runs.items()
    }

    planned: list[str] = []
    if scenarios_dir is not None:
        planned = [p.name for p in sorted(scenarios_dir.iterdir()) if p.is_dir()]

    n_planned_runs = _planned_run_count(planned, by_scenario, len(records), seed_count)
    counts = _count_buckets(records, n_planned=n_planned_runs)
    scenarios_passing_all = sum(
        1
        for row in by_scenario.values()
        if row.get("n_seeds", 0) > 0 and row["passed"] == row["n_seeds"]
    )

    model = records[0]["model"]
    git_sha = records[0].get("git_sha7", "")
    date = records[0].get("started_at", "")[:10]

    header_parts = [model]
    if git_sha:
        header_parts.append(f"@ {git_sha}")
    if date:
        header_parts.append(f"({date})")

    lines: list[str] = [f"### {' '.join(header_parts)}", ""]
    lines += _bucket_rollup_lines(
        counts, len(records), scenarios_passing_all, len(by_scenario)
    )
    lines.append("")
    lines += _grouped_scenario_table_lines(by_scenario, planned)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "step_summary.md").write_text("\n".join(lines) + "\n")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _fmt_mean(v: float | None) -> str:
    if v is None:
        return "—"
    return f"{v:.0f}"


def _fmt_diag(ratio: float | None, n: int | None) -> str:
    if ratio is None:
        return "—"
    base = f"{ratio:.2f}"
    if n is not None:
        correct = round(ratio * n)
        return f"{base} ({correct}/{n})"
    return base
