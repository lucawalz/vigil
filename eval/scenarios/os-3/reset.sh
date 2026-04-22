#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
FILL_PATH="/var/lib/rancher/k3s/eval-fill.img"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "rm -f ${FILL_PATH}"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch"

echo "reset.sh: os-3 seed=${SEED} — node at baseline"
