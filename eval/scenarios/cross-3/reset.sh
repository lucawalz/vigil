#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "systemctl start systemd-resolved.service || true"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch"

echo "reset.sh: cross-3 seed=${SEED} — node at baseline"
