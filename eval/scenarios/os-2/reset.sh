#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-2}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "systemctl start k3s-agent.service || true"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch"

echo "reset.sh: os-2 seed=${SEED} — node at baseline"
