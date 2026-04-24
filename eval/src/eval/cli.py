from __future__ import annotations

import asyncio
import json
import logging
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
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(2)
    except (RuntimeError, FileNotFoundError) as e:
        click.echo(f"ERROR: {e}", err=True)
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


@cli.command("campaign")
@click.option(
    "--scenarios-dir",
    default="eval/scenarios",
    envvar="VIGIL_SCENARIOS_DIR",
    show_envvar=True,
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option("--models", required=True, multiple=True,
              help="Model identifier(s). Repeat flag: --models m1 --models m2.")
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
@click.option("--index", default=None,
              help="Path to runs_index.jsonl (default: {runs_dir}/../runs_index.jsonl).")
@click.option(
    "--timeout",
    "timeout_s",
    default=DEFAULT_TIMEOUT_S,
    type=int,
    envvar="VIGIL_RUN_TIMEOUT_S",
    show_envvar=True,
)
@click.option("--retry-failed", is_flag=True, default=False,
              help="Re-run only combinations listed in failures.jsonl.")
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
    """Execute the full Cartesian product of (scenarios × models × seeds)."""
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
            (sc, sd, md) for sc, sd, md in all_combos
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
            result_path = asyncio.run(run_one(
                scenario_id=scenario,
                seed=seed,
                model=model,
                scenarios_dir=scenarios_dir,
                orchestrator_url=orchestrator_url,
                runs_dir=runs_dir,
                timeout_s=timeout_s,
                verbose=verbose,
            ))
            record = json.loads(result_path.read_text())
            success = "SUCCESS" if record.get("success_rate") else "FAIL"
            mttr = record.get("MTTR_s")
            mttr_s = f"{mttr:.0f}s" if isinstance(mttr, (int, float)) else "?s"
            click.echo(
                f"[{n}/{total}] {scenario}/seed{seed}/{model} — {success} (MTTR={mttr_s})",
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
                f"[{n}/{total}] {scenario}/seed{seed}/{model} — FAILED: {e}",
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
@click.option("--index", default=None,
              help="Path to runs_index.jsonl (default: {runs_dir}/../runs_index.jsonl).")
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
def aggregate_cmd(
    runs_dir: Path | None,
    index: str | None,
    scenarios_dir: Path,
    output_dir: Path,
) -> None:
    """Read completed run JSONs and produce summary.json and REPORT.md."""
    from eval.aggregate import aggregate_runs, write_report

    runs_dir = Path(runs_dir) if runs_dir else Path("eval/runs")
    index_path = Path(index) if index else (runs_dir.parent / "runs_index.jsonl")
    output_dir = Path(output_dir)

    summary = aggregate_runs(runs_dir, index_path, scenarios_dir)
    write_report(summary, output_dir)
    click.echo(f"Written: {output_dir}/summary.json, {output_dir}/REPORT.md")


if __name__ == "__main__":
    cli()
