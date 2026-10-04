from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Mapping
from pathlib import Path

from vigil_lab.guest import guest_ssh_args, ssh_ok, wait_for_ssh
from vigil_lab.proc import LabError, run, wait_until
from vigil_lab.qemu import API_FORWARD_PORT, GUEST_API_PORT, LOOPBACK
from vigil_lab.state import LabContext, LabPaths, LabSettings, write_private

GITHUB_URL = "https://github.com"
GITHUB_REPO_RE = re.compile(r"github\.com[:/]([^/\s]+/[^/\s]+?)(?:\.git)?/?$")
ORCHESTRATOR_PORT = 9099
GUEST_HOST_GATEWAY = "10.0.2.2"
ORCHESTRATOR_URL = f"http://{LOOPBACK}:{ORCHESTRATOR_PORT}"
WEBHOOK_URL = f"http://{GUEST_HOST_GATEWAY}:{ORCHESTRATOR_PORT}/webhook"
ADMIN = "admin"
EVAL_RUNNER = "eval-runner"
FAULT_INJECTION = "fault-injection"
SERVICE_ACCOUNTS = {
    EVAL_RUNNER: "vigil-eval-runner",
    FAULT_INJECTION: "vigil-fault-injection",
}
SERVICE_ACCOUNT_NAMESPACE = "default"
TOKEN_DURATION = "86400s"
GUEST_KUBECONFIG = "/etc/rancher/k3s/k3s.yaml"
GUEST_API_URL = f"https://{LOOPBACK}:{GUEST_API_PORT}"
API_FORWARD_URL = f"https://{LOOPBACK}:{API_FORWARD_PORT}"
LAB_CLUSTER_NAME = "vigil-lab"
MONITORING_NAMESPACE = "monitoring"
WEBHOOK_SECRET_NAME = "vigil-webhook-secret"
FLUX_NAMESPACE = "flux-system"
LAB_SETTINGS_CONFIGMAP = "vigil-lab-settings"
WEBHOOK_URL_KEY = "VIGIL_WEBHOOK_URL"
LAB_CLUSTER_PATH = "./infra/overlays/lab/kubernetes/clusters/lab"
SSH_READY_TIMEOUT_S = 600.0
KUBECONFIG_READY_TIMEOUT_S = 300.0
NODES_READY_TIMEOUT_S = 600.0
READY = "True"
GIT_LS_REMOTE_NO_MATCH = 2
CREDENTIAL_HELPER = (
    '!f() { test "$1" = get && test -n "$GITHUB_TOKEN" && '
    'printf "username=x-access-token\\npassword=%s\\n" "$GITHUB_TOKEN"; }; f'
)
SCRATCH_GIT_CONFIG = {
    "user.name": "eval-harness",
    "user.email": "eval@vigil.local",
    "credential.https://github.com.helper": CREDENTIAL_HELPER,
}


def parse_github_repo(url: str) -> str:
    match = GITHUB_REPO_RE.search(url.strip())
    if match is None:
        raise LabError(
            f"origin {url.strip()!r} is not a GitHub repository; pass --repo owner/name"
        )
    return match.group(1)


def _token_kubeconfig(*, user: str, token: str, ca_data: str) -> str:
    return (
        "apiVersion: v1\n"
        "kind: Config\n"
        "clusters:\n"
        f"- name: {LAB_CLUSTER_NAME}\n"
        "  cluster:\n"
        f"    server: {API_FORWARD_URL}\n"
        f"    certificate-authority-data: {ca_data}\n"
        "users:\n"
        f"- name: {user}\n"
        "  user:\n"
        f"    token: {token}\n"
        "contexts:\n"
        f"- name: {user}@{LAB_CLUSTER_NAME}\n"
        "  context:\n"
        f"    cluster: {LAB_CLUSTER_NAME}\n"
        f"    user: {user}\n"
        f"current-context: {user}@{LAB_CLUSTER_NAME}\n"
    )


def worker_setup_command(repo: str, branch: str) -> str:
    url = shlex.quote(f"{GITHUB_URL}/{repo}")
    quoted = shlex.quote(branch)
    return (
        f"mkdir -p /etc/vigil && printf '%s\\n' {quoted} > /etc/vigil/branch && "
        "if [ ! -d /opt/vigil/.git ]; then "
        f"git clone --branch {quoted} {url} /opt/vigil; "
        f"else git -C /opt/vigil fetch origin && git -C /opt/vigil checkout {quoted} "
        f"&& git -C /opt/vigil reset --hard origin/{quoted}; fi && "
        "ln -sfn /opt/vigil/infra/nixos /opt/nixos-config"
    )


def invoking_checkout(cwd: Path | None = None) -> Path | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def ensure_scratch_clone(paths: LabPaths, repo: str, checkout: Path | None) -> None:
    scratch = paths.repo.resolve()
    if checkout is not None:
        resolved = checkout.resolve()
        if scratch == resolved or resolved in scratch.parents:
            raise LabError(
                f"the lab scratch clone {scratch} lies inside the checkout {resolved}; "
                "set XDG_STATE_HOME to a directory outside the checkout"
            )
    url = f"{GITHUB_URL}/{repo}.git"
    if (paths.repo / ".git").is_dir():
        run(["git", "-C", str(paths.repo), "remote", "set-url", "origin", url])
        run(["git", "-C", str(paths.repo), "fetch", "--quiet", "origin"])
    else:
        run(["git", "clone", "--quiet", url, str(paths.repo)])
    for key, value in SCRATCH_GIT_CONFIG.items():
        run(["git", "-C", str(paths.repo), "config", key, value])


def ensure_branch(repo_dir: Path, branch: str, environ: Mapping[str, str]) -> None:
    probe_result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_dir),
            "ls-remote",
            "--exit-code",
            "--heads",
            "origin",
            branch,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe_result.returncode == 0:
        return
    if probe_result.returncode != GIT_LS_REMOTE_NO_MATCH:
        raise LabError(
            f"git ls-remote for {branch} failed: {probe_result.stderr.strip()}"
        )
    if not environ.get("GITHUB_TOKEN"):
        raise LabError(
            f"branch {branch} does not exist on origin; export GITHUB_TOKEN with "
            "contents write access so the lab can create it from main"
        )
    run(
        [
            "git",
            "-C",
            str(repo_dir),
            "push",
            "--quiet",
            "origin",
            f"origin/main:refs/heads/{branch}",
        ]
    )


def _kubectl(paths: LabPaths, *args: str, input_text: str | None = None) -> str:
    return run(
        ["kubectl", "--kubeconfig", str(paths.kubeconfig(ADMIN)), *args],
        input_text=input_text,
    )


def _apply_generated(paths: LabPaths, *create_args: str) -> None:
    manifest = _kubectl(paths, "create", *create_args, "--dry-run=client", "-o", "yaml")
    _kubectl(paths, "apply", "-f", "-", input_text=manifest)


def _nodes_ready(ctx: LabContext) -> bool:
    try:
        statuses = _kubectl(
            ctx.paths,
            "get",
            "nodes",
            "-o",
            'jsonpath={.items[*].status.conditions[?(@.type=="Ready")].status}',
        )
    except LabError:
        return False
    return statuses.split().count(READY) == len(ctx.plan.hosts)


def refetch_kubeconfigs(ctx: LabContext) -> None:
    control_plane = ctx.plan.control_plane
    wait_until(
        lambda: ssh_ok(ctx.paths, control_plane, f"test -s {GUEST_KUBECONFIG}"),
        KUBECONFIG_READY_TIMEOUT_S,
        "the k3s kubeconfig on the control plane",
    )
    raw = run(guest_ssh_args(ctx.paths, control_plane, f"cat {GUEST_KUBECONFIG}"))
    if GUEST_API_URL not in raw:
        raise LabError(f"the k3s kubeconfig does not name {GUEST_API_URL}")
    write_private(
        ctx.paths.kubeconfig(ADMIN), raw.replace(GUEST_API_URL, API_FORWARD_URL)
    )
    wait_until(lambda: _nodes_ready(ctx), NODES_READY_TIMEOUT_S, "all lab nodes Ready")
    _kubectl(
        ctx.paths, "apply", "-k", str(Path(ctx.flake).parent / "kubernetes" / "rbac")
    )
    ca_data = _kubectl(
        ctx.paths,
        "config",
        "view",
        "--raw",
        "--minify",
        "-o",
        "jsonpath={.clusters[0].cluster.certificate-authority-data}",
    )
    for name, account in SERVICE_ACCOUNTS.items():
        token = _kubectl(
            ctx.paths,
            "create",
            "token",
            account,
            "-n",
            SERVICE_ACCOUNT_NAMESPACE,
            f"--duration={TOKEN_DURATION}",
        ).strip()
        write_private(
            ctx.paths.kubeconfig(name),
            _token_kubeconfig(user=account, token=token, ca_data=ca_data),
        )


def bootstrap(ctx: LabContext, settings: LabSettings) -> None:
    for host in ctx.plan.hosts:
        wait_for_ssh(ctx.paths, host, SSH_READY_TIMEOUT_S)
    refetch_kubeconfigs(ctx)
    _apply_generated(ctx.paths, "namespace", MONITORING_NAMESPACE)
    _apply_generated(
        ctx.paths,
        "secret",
        "generic",
        WEBHOOK_SECRET_NAME,
        "-n",
        MONITORING_NAMESPACE,
        f"--from-file=token={ctx.paths.webhook_secret}",
    )
    for worker in ctx.plan.workers:
        run(
            guest_ssh_args(
                ctx.paths, worker, worker_setup_command(settings.repo, settings.branch)
            ),
            log_file=ctx.paths.log(f"{worker.name}-setup"),
        )
    _apply_generated(ctx.paths, "namespace", FLUX_NAMESPACE)
    _apply_generated(
        ctx.paths,
        "configmap",
        LAB_SETTINGS_CONFIGMAP,
        "-n",
        FLUX_NAMESPACE,
        f"--from-literal={WEBHOOK_URL_KEY}={WEBHOOK_URL}",
    )
    run(
        [
            "bash",
            str(Path(ctx.flake).parent / "scripts" / "flux-sync.sh"),
            f"{GITHUB_URL}/{settings.repo}.git",
            settings.branch,
            LAB_CLUSTER_PATH,
        ],
        env={**os.environ, "KUBECONFIG": str(ctx.paths.kubeconfig(ADMIN))},
        log_file=ctx.paths.log("flux"),
    )
