import json
import os
import shutil
import stat
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest
from vigil_lab import agent
from vigil_lab.addresses import parse_address_plan
from vigil_lab.agent import (
    lab_env,
    load_agent_env_defaults,
    write_lab_env,
    write_ssh_tools,
)
from vigil_lab.guest import GUEST_USER
from vigil_lab.proc import LabError, pid_alive
from vigil_lab.state import LabPaths, LabSettings

BOUNDED_TIMEOUT_S = 20.0
EXITING_COMMAND = ("/bin/sh", "-c", "echo token required; exit 1")
RUNNING_COMMAND = ("/bin/sleep", "30")
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
OWNER_USER = "git-owner"
CALLER_ENV = {
    "PATH": "/usr/bin",
    "HOME": "/home/u",
    "GITHUB_TOKEN": "gh",
    "GITHUB_APP_CLIENT_ID": "Iv1.abc",
    "GITHUB_APP_PRIVATE_KEY_FILE": "/keys/app.pem",
    "OLLAMA_API_KEY": "ok",
    "OLLAMA_BASE_URL": "https://ollama.example.invalid/v1",
    "LLM_MODEL_NAME": "qwen3.5:cloud",
    "ANTHROPIC_API_KEY": "ak",
    "DIAGNOSIS_TIMEOUT_S": "600",
    "AWS_SECRET_ACCESS_KEY": "unrelated",
}


REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_ENV_FILE = REPO_ROOT / "infra" / "agent-env.json"
SHARED_ENV_KEYS = {
    "VIGIL_BLOCK_ALERT_TRIGGERS",
    "LLM_REASONING_EFFORT",
    "DIAGNOSIS_TIMEOUT_S",
    "REMEDIATION_TIMEOUT_S",
    "ORCHESTRATOR_RUN_TIMEOUT_S",
}
SHARED_DEFAULTS = {
    "VIGIL_BLOCK_ALERT_TRIGGERS": "true",
    "LLM_REASONING_EFFORT": "none",
    "DIAGNOSIS_TIMEOUT_S": "111",
    "REMEDIATION_TIMEOUT_S": "222",
    "ORCHESTRATOR_RUN_TIMEOUT_S": "333",
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
        agent_defaults=SHARED_DEFAULTS,
    )


def test_lab_env_applies_the_shared_defaults_under_the_caller_environment(
    tmp_path: Path,
) -> None:
    env = _env(LabPaths(tmp_path))
    assert env["REMEDIATION_TIMEOUT_S"] == "222"
    assert env["ORCHESTRATOR_RUN_TIMEOUT_S"] == "333"
    assert env["LLM_REASONING_EFFORT"] == "none"
    assert env["DIAGNOSIS_TIMEOUT_S"] == CALLER_ENV["DIAGNOSIS_TIMEOUT_S"]


def test_load_agent_env_defaults_reads_the_flat_map(tmp_path: Path) -> None:
    source = tmp_path / "agent-env.json"
    source.write_text(json.dumps(SHARED_DEFAULTS))
    assert load_agent_env_defaults(source) == SHARED_DEFAULTS


@pytest.mark.parametrize(
    "content",
    [None, "{", "[]", '{"A": 1}', '{"A": {"B": "c"}}'],
)
def test_load_agent_env_defaults_names_the_path_when_unusable(
    tmp_path: Path, content: str | None
) -> None:
    source = tmp_path / "agent-env.json"
    if content is not None:
        source.write_text(content)
    with pytest.raises(LabError) as raised:
        load_agent_env_defaults(source)
    assert str(source) in str(raised.value)


def test_shared_env_file_holds_exactly_the_agent_defaults() -> None:
    assert set(load_agent_env_defaults(SHARED_ENV_FILE)) == SHARED_ENV_KEYS


def test_terraform_renders_the_agent_defaults_from_the_shared_file() -> None:
    servers = (REPO_ROOT / "infra" / "terraform" / "servers.tf").read_text()
    assert "agent-env.json" in servers
    assert "local.agent_env_defaults" in servers
    for key in SHARED_ENV_KEYS:
        assert f"{key}=" not in servers


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
        "GITHUB_APP_CLIENT_ID": "Iv1.abc",
        "GITHUB_APP_PRIVATE_KEY_FILE": "/keys/app.pem",
        "OLLAMA_API_KEY": "ok",
        "OLLAMA_BASE_URL": "https://ollama.example.invalid/v1",
        "LLM_MODEL_NAME": "qwen3.5:cloud",
        "ANTHROPIC_API_KEY": "ak",
        "DIAGNOSIS_TIMEOUT_S": "600",
        "LLM_REASONING_EFFORT": "none",
        "REMEDIATION_TIMEOUT_S": "222",
        "ORCHESTRATOR_RUN_TIMEOUT_S": "333",
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
        agent_defaults=SHARED_DEFAULTS,
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


def _start(
    paths: LabPaths, tmp_path: Path, command: tuple[str, ...], monkeypatch
) -> None:
    paths.ensure()
    paths.webhook_secret.write_text("s3cret")
    plan = parse_address_plan(FIXTURE.read_text())
    settings = replace(SETTINGS, checkout=str(tmp_path))
    monkeypatch.setattr(agent, "HEALTHZ_TIMEOUT_S", BOUNDED_TIMEOUT_S)
    agent.start(
        paths,
        plan,
        settings,
        lab_command=LAB_COMMAND,
        ssh_binary="/usr/bin/ssh",
        environ=CALLER_ENV,
        agent_env_file=SHARED_ENV_FILE,
        command=command,
    )


def test_start_reports_an_agent_that_exits_with_its_log(
    tmp_path: Path, monkeypatch
) -> None:
    paths = LabPaths(tmp_path)
    monkeypatch.setattr(agent, "_healthy", lambda: False)
    started = time.monotonic()
    with pytest.raises(LabError) as raised:
        _start(paths, tmp_path, EXITING_COMMAND, monkeypatch)
    assert time.monotonic() - started < BOUNDED_TIMEOUT_S
    assert "token required" in str(raised.value)
    assert str(paths.log(agent.AGENT)) in str(raised.value)


def test_start_returns_once_the_agent_is_healthy(tmp_path: Path, monkeypatch) -> None:
    paths = LabPaths(tmp_path)
    monkeypatch.setattr(agent, "_healthy", lambda: True)
    try:
        _start(paths, tmp_path, RUNNING_COMMAND, monkeypatch)
        assert pid_alive(paths.pid(agent.AGENT))
    finally:
        agent.stop(paths)


def _resolved_ssh(config: Path, home: Path, host: str) -> dict[str, list[str]]:
    result = subprocess.run(
        ["ssh", "-G", "-F", str(config), host],
        env={**os.environ, "HOME": str(home)},
        capture_output=True,
        text=True,
        check=True,
    )
    options: dict[str, list[str]] = {}
    for line in result.stdout.splitlines():
        key, _, value = line.partition(" ")
        options.setdefault(key, []).append(value)
    return options


@pytest.fixture
def owner_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".ssh").mkdir(parents=True)
    (home / ".ssh" / "config").write_text(f"Host github.com\n  User {OWNER_USER}\n")
    return home


@pytest.mark.skipif(shutil.which("ssh") is None, reason="ssh is not installed")
def test_ssh_config_leaves_other_hosts_to_the_owner_setup(
    tmp_path: Path, owner_home: Path
) -> None:
    paths = LabPaths(tmp_path / "lab")
    paths.ensure()
    plan = parse_address_plan(FIXTURE.read_text())
    write_ssh_tools(paths, plan.hosts, "/usr/bin/ssh")
    resolved = _resolved_ssh(paths.root / "ssh_config", owner_home, "github.com")
    assert resolved["user"] == [OWNER_USER]
    assert str(paths.lab_key) not in resolved["identityfile"]
    assert resolved["stricthostkeychecking"] == ["ask"]


@pytest.mark.skipif(shutil.which("ssh") is None, reason="ssh is not installed")
def test_ssh_config_keeps_the_lab_identity_for_lab_hosts(
    tmp_path: Path, owner_home: Path
) -> None:
    paths = LabPaths(tmp_path / "lab")
    paths.ensure()
    plan = parse_address_plan(FIXTURE.read_text())
    write_ssh_tools(paths, plan.hosts, "/usr/bin/ssh")
    worker = next(host for host in plan.hosts if host.name == "vigil-worker-1")
    resolved = _resolved_ssh(paths.root / "ssh_config", owner_home, worker.name)
    assert resolved["user"] == [GUEST_USER]
    assert resolved["port"] == [str(worker.ssh_port)]
    assert resolved["identityfile"] == [str(paths.lab_key)]
    assert resolved["stricthostkeychecking"] == ["false"]


def test_ssh_config_scopes_shared_options_to_the_lab_hosts(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    plan = parse_address_plan(FIXTURE.read_text())
    write_ssh_tools(paths, plan.hosts, "/usr/bin/ssh")
    text = (paths.root / "ssh_config").read_text()
    names = " ".join(host.name for host in plan.hosts)
    assert f"Host {names}\n  User {GUEST_USER}\n" in text
    assert "Host *\n" not in text
    assert text.endswith("Match all\n  Include ~/.ssh/config\n")


def test_ssh_config_never_asks_for_a_password(tmp_path: Path) -> None:
    paths = LabPaths(tmp_path)
    paths.ensure()
    plan = parse_address_plan(FIXTURE.read_text())
    write_ssh_tools(paths, plan.hosts, "/usr/bin/ssh")
    assert "  BatchMode yes\n" in (paths.root / "ssh_config").read_text()
