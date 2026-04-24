#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
FILL_PATH="/var/lib/rancher/k3s/eval-fill.img"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "rm -f ${FILL_PATH} && printf '{ }\n' > /opt/nixos-config/hosts/hetzner-worker-1/bad-module.nix"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch --flake /opt/nixos-config#hetzner-worker-1"

echo "reset.sh: os-3 seed=${SEED} — node at baseline"
