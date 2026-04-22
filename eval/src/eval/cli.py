from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import click

from eval.harness import DEFAULT_ORCHESTRATOR_URL, DEFAULT_TIMEOUT_S, run_one


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
    "--verbose", "-v",
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
    os.environ["LLM_MODEL_NAME"] = model

    try:
        result_path = asyncio.run(
            run_one(
                scenario_id=scenario,
                seed=seed,
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


if __name__ == "__main__":
    cli()
