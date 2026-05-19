#!/usr/bin/env bash
set -euo pipefail

: "${SSH_KEY_PATH:?SSH_KEY_PATH must be set}"

SEED="${1:-1}"
TARGET_HOST="hetzner-worker-1"
SSH_OPTS=(-i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

ssh "${SSH_OPTS[@]}" "root@${TARGET_HOST}" \
  "systemctl start --no-block vigil-auto-reconcile.service"

sleep 1

TIMEOUT=180
ELAPSED=0
while ssh "${SSH_OPTS[@]}" "root@${TARGET_HOST}" \
    "systemctl is-active vigil-auto-reconcile.service" 2>/dev/null | grep -q "^active"; do
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "reset.sh: os-1g timeout waiting for auto-reconciler" >&2
    break
  fi
done

echo "reset.sh: os-1g seed=${SEED}: worker at baseline"
