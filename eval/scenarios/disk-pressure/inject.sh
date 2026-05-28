#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-2}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" 'bash -s' <<'REMOTE'
set -euo pipefail
read -r total avail < <(df -B1 --output=size,avail / | awk 'NR==2{print $1, $2}')
fill=$(( avail - total / 20 ))
if [ "$fill" -le 0 ]; then
  echo "inject: disk already past 95% threshold, skipping" >&2
  exit 0
fi
rm -f /var/eval-fill.img
fallocate -l "$fill" /var/eval-fill.img
REMOTE

echo "inject.sh: disk-pressure seed=${SEED} complete"
