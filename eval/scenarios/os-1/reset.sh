#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-vigil-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
CONFIG_DIR="/opt/nixos-config/hosts/vigil-worker-1"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "systemctl start vigil-auto-reconcile.timer || true"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "printf '{ }\n' > ${CONFIG_DIR}/bad-module.nix && sed -i '/bad-module.nix/d' ${CONFIG_DIR}/default.nix || true"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "flock /var/lock/vigil-nixos-rebuild nixos-rebuild switch --flake /opt/nixos-config#\$(cat /etc/vigil/flake-attr)"

echo "reset.sh: os-1 seed=${SEED} - node at baseline"
