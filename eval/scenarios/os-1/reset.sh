#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
CONFIG_DIR="/etc/nixos"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "rm -f ${CONFIG_DIR}/bad-module.nix"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "sed -i '/bad-module.nix/d' ${CONFIG_DIR}/configuration.nix || true"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch"

echo "reset.sh: os-1 seed=${SEED} — node at baseline"
