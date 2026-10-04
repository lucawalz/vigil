import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "infra/scripts/flux-sync.sh"
REPO_URL = "https://github.com/example/vigil.git"
BRANCH = "eval/123/k8s-1"
SYNC_PATH = "./infra/overlays/lab/kubernetes/clusters/lab"
EXECUTABLE = 0o755


def _recording_stub(bin_dir: Path, name: str, log: Path) -> None:
    stub = bin_dir / name
    stub.write_text(f'#!/bin/sh\necho "{name} $*" >> "{log}"\n')
    stub.chmod(EXECUTABLE)


def test_flux_sync_tracks_the_branch_over_public_https(tmp_path: Path) -> None:
    log = tmp_path / "calls.log"
    for name in ("flux", "kubectl"):
        _recording_stub(tmp_path, name, log)
    subprocess.run(
        ["bash", str(SCRIPT), REPO_URL, BRANCH, SYNC_PATH],
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"},
        check=True,
    )
    install, pin, source, kustomization = log.read_text().splitlines()
    assert install.startswith("flux install")
    assert pin.startswith("kubectl -n flux-system patch deployment source-controller")
    assert f"--url={REPO_URL}" in source and f"--branch={BRANCH}" in source
    assert source.startswith("flux create source git flux-system")
    assert "--secret-ref" not in source
    assert kustomization.startswith("flux create kustomization flux-system")
    assert f"--path={SYNC_PATH}" in kustomization
