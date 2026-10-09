# infra/lab

Lab runner that boots the NixOS host definitions as three qemu VMs: `vigil-control-plane-1`, `vigil-worker-1` and `vigil-worker-2`. It uses HVF on Apple silicon macOS and KVM on x86_64 Linux, including GitHub-hosted `ubuntu-latest` runners. The orchestrator and the four MCP servers run natively next to the VMs.

## Commands

Run from a vigil checkout:

```bash
nix run ./infra/nixos#lab -- up                 # golden disks, VMs, k3s, Flux on branch eval/lab
nix run ./infra/nixos#lab -- agent start        # orchestrator on http://127.0.0.1:9099
set -a; . ${XDG_STATE_HOME:-~/.local/state}/vigil-lab/lab.env; set +a
uv run vigil-eval run --scenario k8s-1g --seed 1 --model qwen3.5:cloud
nix run ./infra/nixos#lab -- reset              # fresh cluster from the golden disks
nix run ./infra/nixos#lab -- down               # stop every lab process, keep the state
nix run ./infra/nixos#lab -- destroy            # stop every lab process, delete the state
```

`up --no-golden` installs the disks in place and skips the golden copies (the runner mode); a lab started this way returns to a fresh cluster through `destroy` and `up`. `--repo owner/name` and `--branch` choose what the guests and Flux track; the defaults are the `origin` remote and `eval/lab`. `up` creates a missing branch from `main` and then needs `GITHUB_TOKEN` with contents write access. Flux is installed and pointed at the branch by [`infra/scripts/flux-sync.sh`](../scripts/flux-sync.sh), the same script the Hetzner eval cluster uses.

`agent start` passes `GITHUB_TOKEN`, the run timeout variables and the `OLLAMA_*`, `LLM_*` and `ANTHROPIC_*` variables from the calling shell to the orchestrator and writes `lab.env` with the same keys the eval agent host uses. `agent stop` and `agent restart` stop or restart the orchestrator.

## Requirements

- Nix with flakes. The lab ignores the `builders` setting of the Nix configuration; on macOS the aarch64-linux closures build on a local `darwin.linux-builder` VM that starts and stops around each image build and needs no sudo.
- On macOS, at least 45 percent free memory as reported by `memory_pressure` before `up` or `reset` starts lab VMs, with the lab's own VMs stopped, and free disk for three 10 GB sparse qcow2 working disks plus their golden copies in the state directory, the pinned installer ISO and the Nix store.

## State

`${XDG_STATE_HOME:-~/.local/state}/vigil-lab/` (mode 0700) holds the keys, golden and working disks, sockets, kubeconfigs, the scratch clone used as `VIGIL_REPO_ROOT`, `lab.env`, run records and logs. The lab never writes to the tracked files of the invoking checkout.

## Network

| Host | Node IP | Forward |
|---|---|---|
| `vigil-control-plane-1` | `10.250.0.10` | ssh `127.0.0.1:2210`, API `127.0.0.1:16443` |
| `vigil-worker-1` | `10.250.0.11` | ssh `127.0.0.1:2211` |
| `vigil-worker-2` | `10.250.0.12` | ssh `127.0.0.1:2212` |

The VMs share an L2 segment through a Unix-socket hub in the state directory. Guests reach the native orchestrator at `10.0.2.2:9099`. The address plan comes from [`infra/inventory.json`](../inventory.json).
