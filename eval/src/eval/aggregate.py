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


def _scenario_group(scenario_id: str) -> str:
    for prefix in ("k8s-", "os-", "cross-"):
        if scenario_id.startswith(prefix):
            return prefix.rstrip("-")
    return "misc"


def _load_records(runs_dir: Path, index_path: Path) -> list[dict]:
    records: list[dict] = []
    if not index_path.exists():
        return records
    with index_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            idx_rec = json.loads(line)
            run_file = runs_dir / f"{idx_rec['run_id']}.json"
            if run_file.exists():
                records.append(json.loads(run_file.read_text()))
            else:
                log.warning("run JSON missing for %s; skipping", idx_rec["run_id"])
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
    return data.get("root_cause_layer")


def aggregate_runs(
    runs_dir: Path, index_path: Path, scenarios_dir: Path
) -> dict[str, Any]:
    """Compute per-model and per-scenario metric tables plus escalation accuracy."""
    records = _load_records(runs_dir, index_path)
    planned_scenarios: list[str] = sorted(
        p.name for p in scenarios_dir.iterdir() if p.is_dir()
    ) if scenarios_dir.is_dir() else []
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

    model_summary: dict[str, dict] = {}
    for model, runs in by_model.items():
        successes = [r for r in runs if r.get("success_rate")]
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
        mean_mttr, std_mttr = _mean_std(mttrs)
        n_attempts = len(non_aborts)
        model_summary[model] = {
            "n_runs": len(runs),
            "n_attempts": n_attempts,
            "success_rate": len(successes) / len(runs) if runs else 0.0,
            "success_rate_given_attempt": (
                len(successes) / n_attempts if n_attempts else None
            ),
            "mean_MTTR_s": mean_mttr,
            "std_MTTR_s": std_mttr,
            "diagnosis_accuracy": (
                len(diag_correct) / len(diag_acc) if diag_acc else None
            ),
            "diag_n": len(diag_acc),
            "destructive_repair_rate": len(dest) / len(runs) if runs else 0.0,
            "rollback_triggered_rate": len(rollbacks) / len(runs) if runs else 0.0,
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

    scenario_summary: dict[str, dict] = {}
    escalation: dict[str, dict] = {}
    for scenario, runs in by_scenario.items():
        successes = [r for r in runs if r.get("success_rate")]
        mttrs = [r["MTTR_s"] for r in runs if isinstance(r.get("MTTR_s"), (int, float))]
        mean_mttr, std_mttr = _mean_std(mttrs)
        scenario_summary[scenario] = {
            "n_runs": len(runs),
            "success_rate": len(successes) / len(runs) if runs else 0.0,
            "mean_MTTR_s": mean_mttr,
            "std_MTTR_s": std_mttr,
        }
        layer = _layer_for_scenario(scenarios_dir, scenario)
        if layer is not None:
            scored = [r for r in runs if r.get("diagnosis_accuracy") is not None]
            correct = [r for r in scored if r["diagnosis_accuracy"]]
            per_model: dict[str, dict] = {}
            for r in scored:
                m = r["model"]
                slot = per_model.setdefault(m, {"correct": 0, "total": 0})
                slot["total"] += 1
                if r["diagnosis_accuracy"]:
                    slot["correct"] += 1
            escalation[scenario] = {
                "layer": layer,
                "correct": len(correct),
                "total": len(scored),
                "accuracy": (len(correct) / len(scored)) if scored else None,
                "per_model": per_model,
            }
        else:
            escalation[scenario] = {"layer": None, "accuracy": None}

    return {
        "by_model": model_summary,
        "by_scenario": scenario_summary,
        "escalation": escalation,
        "totals": {
            "n": len(records),
            "n_models": len(by_model),
            "n_scenarios": len(by_scenario),
        },
        "planned_scenarios": planned_scenarios,
    }


def write_report(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

    lines: list[str] = []
    lines.append("# Phase 9 — Eval Campaign Aggregation Report")
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
        "Diag. Accuracy | Destructive % | Rollback % | "
        "Mean In/Out Tokens | Mean Tool Calls |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|---:|")
    for m, row in summary["by_model"].items():
        lines.append(
            f"| {m} | {row['n_runs']} | "
            f"{row['success_rate']:.2f} | "
            f"{_fmt(row['mean_MTTR_s'])} | {_fmt(row['std_MTTR_s'])} | "
            f"{_fmt_diag(row['diagnosis_accuracy'], row.get('diag_n'))} | "
            f"{row['destructive_repair_rate']:.2f} | "
            f"{row['rollback_triggered_rate']:.2f} | "
            f"{_fmt(row['mean_input_tokens'])}/{_fmt(row['mean_output_tokens'])} | "
            f"{_fmt(row['mean_tool_calls'])} |"
        )
    lines.append("")

    lines.append("## Per-Scenario Summary")
    lines.append("")
    lines.append("| Scenario | N | Success Rate | Mean MTTR (s) | Std MTTR (s) |")
    lines.append("|---|---:|---:|---:|---:|")
    by_scenario = summary["by_scenario"]
    planned: list[str] = summary.get("planned_scenarios") or []
    scenario_keys = planned if planned else sorted(by_scenario)
    ordered_scenarios: list[str] = []
    for group in _GROUP_ORDER:
        ordered_scenarios.extend(
            s for s in scenario_keys if _scenario_group(s) == group
        )
    for s in scenario_keys:
        if s not in ordered_scenarios:
            ordered_scenarios.append(s)
    for s in ordered_scenarios:
        row = by_scenario.get(s)
        if row is None:
            lines.append(f"| {s} | no data | — | — | — |")
        else:
            lines.append(
                f"| {s} | {row['n_runs']} | {row['success_rate']:.2f} | "
                f"{_fmt(row['mean_MTTR_s'])} | {_fmt(row['std_MTTR_s'])} |"
            )
    lines.append("")

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
    lines.append(
        "_Note: std values computed from 3 seeds per cell are approximate "
        "(n=3); treat as directional only._"
    )

    (output_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


def write_step_summary(
    runs_dir: Path,
    index_path: Path,
    output_dir: Path,
    scenarios_dir: Path | None = None,
) -> None:
    records = _load_records(runs_dir, index_path)
    if not records:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "step_summary.md").write_text("No run data available.\n")
        return

    by_group: dict[str, dict[str, dict | None]] = {}
    for r in records:
        g = _scenario_group(r["scenario"])
        by_group.setdefault(g, {})[r["scenario"]] = r

    if scenarios_dir is not None:
        for sid in (p.name for p in sorted(scenarios_dir.iterdir()) if p.is_dir()):
            g = _scenario_group(sid)
            by_group.setdefault(g, {}).setdefault(sid, None)

    n_remediated = sum(1 for r in records if r.get("success_rate"))
    n_aborted = sum(1 for r in records if r["outcome"] == "abort")
    n_total = sum(len(scs) for scs in by_group.values())

    model = records[0]["model"]
    git_sha = records[0].get("git_sha7", "")
    date = records[0].get("started_at", "")[:10]

    header_parts = [model]
    if git_sha:
        header_parts.append(f"@ {git_sha}")
    if date:
        header_parts.append(f"({date})")

    lines: list[str] = [
        f"### {' '.join(header_parts)}",
        "",
        f"{n_remediated} of {n_total} scenarios remediated; {n_aborted} aborted.",
        "",
    ]

    for group in _GROUP_ORDER:
        if group not in by_group:
            continue
        scenarios = by_group[group]
        lines += [
            f"#### {_GROUP_LABELS[group]}",
            "",
            "| scenario | outcome | remediated | diagnosis"
            " | MTTR (s) | iterations | tool calls |",
            "|----------|---------|------------|-----------|----------:|----------:|----------:|",
        ]
        for sid in sorted(scenarios):
            r = scenarios[sid]
            if r is None:
                lines.append(f"| {sid} | no data | — | — | — | — | — |")
                continue
            if r["outcome"] == "abort":
                outcome_cell = "abort"
                remediated_cell = "—"
            else:
                outcome_cell = "pass"
                remediated_cell = "yes" if r.get("success_rate") else "no"
            diag = r.get("diagnosis_accuracy")
            if diag is True:
                diag_cell = "correct"
            elif diag is False:
                diag_cell = "incorrect"
            else:
                diag_cell = "—"
            mttr = r.get("MTTR_s")
            mttr_cell = f"{mttr:.0f}" if isinstance(mttr, (int, float)) else "—"
            iters = r.get("iteration_count", "—")
            tools = r.get("total_tool_calls", "—")
            lines.append(
                f"| {sid} | {outcome_cell} | {remediated_cell} | {diag_cell}"
                f" | {mttr_cell} | {iters} | {tools} |"
            )
        lines.append("")

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "step_summary.md").write_text("\n".join(lines) + "\n")


def _fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def _fmt_diag(ratio: float | None, n: int | None) -> str:
    if ratio is None:
        return "—"
    base = f"{ratio:.2f}"
    if n is not None:
        correct = round(ratio * n)
        return f"{base} ({correct}/{n})"
    return base
