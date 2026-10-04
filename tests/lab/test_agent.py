import os
import stat
import subprocess
from pathlib import Path

from vigil_lab.addresses import parse_address_plan
from vigil_lab.agent import lab_env, write_lab_env
from vigil_lab.state import LabPaths, LabSettings

FIXTURE = Path(__file__).parent / "fixtures" / "addresses.json"
SETTINGS = LabSettings(
    repo="example/vigil",
    branch="eval/lab",
    target="lab",
    golden=True,
    checkout="/work/vigil",
)
LAB_COMMAND = "/nix/store/x-lab/bin/lab"
PRIVATE_FILE = 0o600
CALLER_ENV = {
    "PATH": "/usr/bin",
    "HOME": "/home/u",
    "GITHUB_TOKEN": "gh",
    "OLLAMA_API_KEY": "ok",
    "OLLAMA_BASE_URL": "https://ollama.example.invalid/v1",
    "LLM_MODEL_NAME": "qwen3.5:cloud",
    "ANTHROPIC_API_KEY": "ak",
    "DIAGNOSIS_TIMEOUT_S": "600",
    "AWS_SECRET_ACCESS_KEY": "unrelated",
}


def _env(paths: LabPaths) -> dict[str, str]:
    plan = parse_address_plan(FIXTURE.read_text())
    return lab_env(
        paths,
        plan,
        SETTINGS,
        webhook_secret="s3cret",
        lab_command=LAB_COMMAND,
        environ=CALLER_ENV,
    )


def test_lab_env_matches_the_agent_contract(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    assert _env(paths) == {
        "SSH_HOSTS": "vigil-worker-1:2211,vigil-worker-2:2212",
        "SSH_USER": "root",
        "SSH_KEY_PATH": str(tmp_path / "keys" / "lab_ed25519"),
        "EVAL_RUNNER_KUBECONFIG": str(tmp_path / "kube" / "eval-runner.yaml"),
        "FAULT_INJECTION_KUBECONFIG": str(tmp_path / "kube" / "fault-injection.yaml"),
        "KUBECONFIG": str(tmp_path / "kube" / "eval-runner.yaml"),
        "VIGIL_REPO_ROOT": str(tmp_path / "repo"),
        "VIGIL_EVAL_BRANCH": "eval/lab",
        "VIGIL_ORCHESTRATOR_URL": "http://127.0.0.1:9099",
        "VIGIL_ORCHESTRATOR_RESTART_CMD": f"{LAB_COMMAND} agent restart",
        "VIGIL_BLOCK_ALERT_TRIGGERS": "true",
        "PROM_POLLER_ENABLED": "false",
        "VIGIL_EVAL_TARGET": "lab",
        "REPO_URL": "https://github.com/example/vigil.git",
        "VIGIL_WEBHOOK_SECRET": "s3cret",
        "EVAL_RUNS_DIR": str(tmp_path / "runs"),
        "VIGIL_SCENARIOS_DIR": "/work/vigil/eval/scenarios",
        "PATH": f"{tmp_path / 'bin'}{os.pathsep}/usr/bin",
        "GITHUB_TOKEN": "gh",
        "OLLAMA_API_KEY": "ok",
        "OLLAMA_BASE_URL": "https://ollama.example.invalid/v1",
        "LLM_MODEL_NAME": "qwen3.5:cloud",
        "ANTHROPIC_API_KEY": "ak",
        "DIAGNOSIS_TIMEOUT_S": "600",
    }


def test_lab_env_prepends_the_bin_directory_once(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    plan = parse_address_plan(FIXTURE.read_text())
    already_first = {**CALLER_ENV, "PATH": f"{paths.bin}{os.pathsep}/usr/bin"}
    env = lab_env(
        paths,
        plan,
        SETTINGS,
        webhook_secret="s3cret",
        lab_command=LAB_COMMAND,
        environ=already_first,
    )
    assert env["PATH"] == f"{paths.bin}{os.pathsep}/usr/bin"


def test_lab_env_repo_root_is_the_scratch_clone(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    repo_root = Path(_env(paths)["VIGIL_REPO_ROOT"])
    assert repo_root == paths.repo
    assert repo_root.is_relative_to(paths.root)
    assert str(repo_root) != SETTINGS.checkout


def test_lab_env_file_is_private_and_sources_in_bash(tmp_path: Path) -> None:
    env_file = tmp_path / "lab.env"
    write_lab_env(
        env_file,
        {"VIGIL_ORCHESTRATOR_RESTART_CMD": "/x/lab agent restart", "QUOTED": "it's"},
    )
    assert stat.S_IMODE(env_file.stat().st_mode) == PRIVATE_FILE
    out = subprocess.run(
        [
            "bash",
            "-c",
            f'set -a; . "{env_file}"; set +a; '
            'printf "%s|%s" "$VIGIL_ORCHESTRATOR_RESTART_CMD" "$QUOTED"',
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert out == "/x/lab agent restart|it's"
