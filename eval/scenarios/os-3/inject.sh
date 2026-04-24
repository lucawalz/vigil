#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
FILL_PATH="/var/lib/rancher/k3s/eval-fill.img"
FILL_SIZE="${FILL_SIZE:-20G}"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "test -f ${FILL_PATH} || fallocate -l ${FILL_SIZE} ${FILL_PATH}"

echo "inject.sh: os-3 seed=${SEED} complete"
