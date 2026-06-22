from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from eval.campaign import combinations, completed_run_ids
from eval.harness import DEFAULT_ORCHESTRATOR_URL, DEFAULT_TIMEOUT_S, run_one
from eval.scenario import load_scenarios


@click.group()
def cli() -> None:
    """Vigil eval harness."""


@cli.command("run")
@click.option("--scenario", required=True, help="Scenario id, e.g. k8s-1")
@click.option("--seed", required=True, type=int, help="Run counter (1, 2, 3)")
@click.option(
    "--model", required=True, help="Model identifier passed through to Orchestrator"
)
@click.option(
    "--timeout",
    "timeout_s",
    default=DEFAULT_TIMEOUT_S,
    type=int,
    envvar="VIGIL_RUN_TIMEOUT_S",
    show_envvar=True,
    help="Seconds to poll for the run result file before exiting non-zero.",
)
@click.option(
    "--orchestrator-url",
    default=DEFAULT_ORCHESTRATOR_URL,
    envvar="VIGIL_ORCHESTRATOR_URL",
    show_envvar=True,
)
@click.option(
    "--scenarios-dir",
    default="eval/scenarios",
    envvar="VIGIL_SCENARIOS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--runs-dir",
    default=None,
    envvar="EVAL_RUNS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Defaults to eval/runs (matches Orchestrator default).",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Stream script output and log progress to stderr.",
)
def run_cmd(
    scenario: str,
    seed: int,
    model: str,
    timeout_s: int,
    orchestrator_url: str,
    scenarios_dir: Path,
    runs_dir: Path | None,
    verbose: bool,
) -> None:
    """Execute one eval run: reset -> inject -> POST -> poll -> print metrics."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        result_path = asyncio.run(
            run_one(
                scenario_id=scenario,
                seed=seed,
                model=model,
                scenarios_dir=scenarios_dir,
                orchestrator_url=orchestrator_url,
                runs_dir=runs_dir,
                timeout_s=timeout_s,
                verbose=verbose,
            )
        )
    except TimeoutError as e:
        resolved_runs_dir = Path(runs_dir) if runs_dir else Path("eval/runs")
        result_path = resolved_runs_dir / f"{_run_id_for(scenario, seed, model)}.json"
        if result_path.exists():
            click.echo(
                "NOTE: orchestrator result appeared after the wait deadline; using it",
                err=True,
            )
        else:
            click.echo(f"ERROR: {e}", err=True)
            _write_setup_error_record(
                scenario,
                seed,
                model,
                resolved_runs_dir,
                str(e),
                outcome="harness_timeout",
                started_at=started_at,
            )
            sys.exit(2)
    except (RuntimeError, FileNotFoundError) as e:
        click.echo(f"ERROR: {e}", err=True)
        resolved_runs_dir = Path(runs_dir) if runs_dir else Path("eval/runs")
        _write_setup_error_record(
            scenario,
            seed,
            model,
            resolved_runs_dir,
            str(e),
            started_at=started_at,
        )
        sys.exit(1)

    record = json.loads(result_path.read_text())
    click.echo(
        json.dumps(
            {
                "run_id": record["run_id"],
                "outcome": record["outcome"],
                "success_rate": record.get("success_rate"),
                "MTTR_s": record.get("MTTR_s"),
                "iteration_count": record.get("iteration_count"),
                "result_file": str(result_path),
            },
            indent=2,
        )
    )


def _run_id_for(scenario_id: str, seed: int, model: str) -> str:
    try:
        sha7 = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        sha7 = "unknown"
    safe_model = re.sub(r"[^a-zA-Z0-9_-]", "-", model)
    return f"{scenario_id}_{seed}_{safe_model}_{sha7}"


def _write_setup_error_record(
    scenario_id: str,
    seed: int,
    model: str,
    runs_dir: Path,
    error_msg: str,
    outcome: str = "setup_error",
    started_at: str | None = None,
) -> bool:
    run_id = _run_id_for(scenario_id, seed, model)
    result_path = runs_dir / f"{run_id}.json"
    if result_path.exists():
        return False

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runs_dir.mkdir(parents=True, exist_ok=True)
    record: dict = {
        "run_id": run_id,
        "scenario": scenario_id,
        "seed": seed,
        "model": model,
        "outcome": outcome,
        "success_rate": False,
        "diagnosis_accuracy": None,
        "MTTR_s": None,
        "destructive_repair": False,
        "rollback_triggered": False,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_tool_calls": 0,
        "iteration_count": 0,
        "autonomy_level": "full",
        "actions_taken": [],
        "forbidden_action_violations": [],
        "started_at": started_at or now_str,
        "ended_at": now_str,
        "setup_error": error_msg[:500],
    }
    result_path.write_text(json.dumps(record, indent=2))

    index_path = runs_dir.parent / "runs_index.jsonl"
    index_entry = {
        "run_id": run_id,
        "scenario": scenario_id,
        "seed": seed,
        "model": model,
        "outcome": outcome,
        "success_rate": False,
    }
    with index_path.open("a") as fh:
        fh.write(json.dumps(index_entry) + "\n")
    return True


@cli.command("campaign")
@click.option(
    "--scenarios-dir",
    default="eval/scenarios",
    envvar="VIGIL_SCENARIOS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--models",
    required=True,
    multiple=True,
    help="Model identifier(s). Repeat flag: --models m1 --models m2.",
)
@click.option("--seeds", default=(1, 2, 3), multiple=True, type=int, show_default=True)
@click.option(
    "--runs-dir",
    default=None,
    envvar="EVAL_RUNS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Defaults to eval/runs (matches Orchestrator default).",
)
@click.option(
    "--orchestrator-url",
    default=DEFAULT_ORCHESTRATOR_URL,
    envvar="VIGIL_ORCHESTRATOR_URL",
    show_envvar=True,
)
@click.option(
    "--index",
    default=None,
    help="Path to runs_index.jsonl (default: {runs_dir}/../runs_index.jsonl).",
)
@click.option(
    "--timeout",
    "timeout_s",
    default=DEFAULT_TIMEOUT_S,
    type=int,
    envvar="VIGIL_RUN_TIMEOUT_S",
    show_envvar=True,
)
@click.option(
    "--retry-failed",
    is_flag=True,
    default=False,
    help="Re-run only combinations listed in failures.jsonl.",
)
@click.option("--verbose", "-v", is_flag=True, default=False)
def campaign_cmd(
    scenarios_dir: Path,
    models: tuple,
    seeds: tuple,
    runs_dir: Path | None,
    orchestrator_url: str,
    index: str | None,
    timeout_s: int,
    retry_failed: bool,
    verbose: bool,
) -> None:
    """Run all (scenarios × models × seeds) combinations; pause on quota exhaustion."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )

    runs_dir = Path(runs_dir) if runs_dir else Path("eval/runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    index_path = Path(index) if index else (runs_dir.parent / "runs_index.jsonl")
    failures_path = runs_dir / "failures.jsonl"

    if retry_failed:
        combos = _load_failed_combinations(failures_path)
    else:
        scenario_ids = [s.id for s in load_scenarios(scenarios_dir)]
        all_combos = list(combinations(scenario_ids, list(seeds), list(models)))
        done = completed_run_ids(index_path)
        combos = [
            (sc, sd, md)
            for sc, sd, md in all_combos
            if not any(rid.startswith(f"{sc}_{sd}_{md}_") for rid in done)
        ]

    total = len(combos)
    click.echo(
        f"Running {total} combinations (runs_dir={runs_dir}, index={index_path})",
        err=True,
    )

    succeeded_this_session: set[tuple[str, int, str]] = set()

    for n, (scenario, seed, model) in enumerate(combos, start=1):
        try:
            result_path = asyncio.run(
                run_one(
                    scenario_id=scenario,
                    seed=seed,
                    model=model,
                    scenarios_dir=scenarios_dir,
                    orchestrator_url=orchestrator_url,
                    runs_dir=runs_dir,
                    timeout_s=timeout_s,
                    verbose=verbose,
                )
            )
            record = json.loads(result_path.read_text())
            if record.get("outcome") == "quota_exhausted":
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                checkpoint = {
                    "stopped_at": now_str,
                    "reason": "quota_exhausted",
                    "completed_n": n - 1,
                    "remaining_combos": [
                        {"scenario": sc, "seed": sd, "model": md}
                        for sc, sd, md in combos[n - 1 :]
                    ],
                }
                checkpoint_path = runs_dir / "quota_checkpoint.json"
                checkpoint_path.write_text(json.dumps(checkpoint, indent=2))
                msg = (
                    f"[{n}/{total}] {scenario}/seed{seed}/{model} - QUOTA_EXHAUSTED: "
                    f"campaign paused. Resume with --resume "
                    f"(checkpoint: {checkpoint_path})"
                )
                click.echo(msg, err=True)
                break
            run_id = record["run_id"]
            trace_path = runs_dir / f"{run_id}_trace.jsonl"
            success = "SUCCESS" if record.get("success_rate") else "FAIL"
            mttr = record.get("MTTR_s")
            mttr_s = f"{mttr:.0f}s" if isinstance(mttr, (int, float)) else "?s"
            click.echo(
                f"[{n}/{total}] {scenario}/seed{seed}/{model}"
                f" - {success} (MTTR={mttr_s})"
                f" | trace: {trace_path}",
                err=True,
            )
            succeeded_this_session.add((scenario, seed, model))
        except Exception as e:
            failure = {
                "scenario": scenario,
                "seed": seed,
                "model": model,
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "error": str(e),
            }
            with failures_path.open("a") as fh:
                fh.write(json.dumps(failure) + "\n")
            click.echo(
                f"[{n}/{total}] {scenario}/seed{seed}/{model} - FAILED: {e}",
                err=True,
            )

    if retry_failed and succeeded_this_session:
        _prune_failures(failures_path, succeeded_this_session)


def _load_failed_combinations(failures_path: Path) -> list[tuple[str, int, str]]:
    if not failures_path.exists():
        return []
    combos: list[tuple[str, int, str]] = []
    seen: set[tuple[str, int, str]] = set()
    with failures_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = (rec["scenario"], int(rec["seed"]), rec["model"])
            if key not in seen:
                seen.add(key)
                combos.append(key)
    return combos


def _prune_failures(failures_path: Path, succeeded: set[tuple[str, int, str]]) -> None:
    if not failures_path.exists():
        return
    kept: list[str] = []
    with failures_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            key = (rec["scenario"], int(rec["seed"]), rec["model"])
            if key not in succeeded:
                kept.append(line)
    if kept:
        failures_path.write_text("\n".join(kept) + "\n")
    else:
        failures_path.unlink(missing_ok=True)


@cli.command("aggregate")
@click.option(
    "--runs-dir",
    default=None,
    envvar="EVAL_RUNS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--index",
    default=None,
    help="Path to runs_index.jsonl (default: {runs_dir}/../runs_index.jsonl).",
)
@click.option(
    "--scenarios-dir",
    default="eval/scenarios",
    envvar="VIGIL_SCENARIOS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--output-dir",
    default="eval/results",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--seed-count",
    default=None,
    type=int,
    envvar="VIGIL_SEED_COUNT",
    show_envvar=True,
    help="Seeds requested per scenario; sizes the planned-runs denominator.",
)
def aggregate_cmd(
    runs_dir: Path | None,
    index: str | None,
    scenarios_dir: Path,
    output_dir: Path,
    seed_count: int | None,
) -> None:
    """Read completed run JSONs and produce summary.json, REPORT.md,
    and step_summary.md."""
    from eval.aggregate import aggregate_runs, write_report, write_step_summary

    runs_dir = Path(runs_dir) if runs_dir else Path("eval/runs")
    index_path = Path(index) if index else (runs_dir.parent / "runs_index.jsonl")
    output_dir = Path(output_dir)

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir, seed_count)
    write_report(summary, output_dir)
    write_step_summary(runs_dir, index_path, output_dir, scenarios_dir, seed_count)
    click.echo(
        f"Written: {output_dir}/summary.json,"
        f" {output_dir}/REPORT.md, {output_dir}/step_summary.md"
    )


if __name__ == "__main__":
    cli()
