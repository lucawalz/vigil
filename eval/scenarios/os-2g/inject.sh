#!/usr/bin/env bash
set -euo pipefail

: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"
: "${SSH_KEY_PATH:?SSH_KEY_PATH must be set}"

SEED="${1:-1}"
TARGET_HOST="hetzner-worker-1"
NIX_CONFIG="$VIGIL_REPO_ROOT/infra/nixos/hosts/hetzner-worker-1/default.nix"
SSH_OPTS=(-i "$SSH_KEY_PATH" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null)

git -C "$VIGIL_REPO_ROOT" checkout -- "$NIX_CONFIG" 2>/dev/null || true

python3 - "$NIX_CONFIG" <<'PYEOF'
import sys
path = sys.argv[1]
lines = open(path).readlines()
idx = len(lines) - 1
while idx >= 0 and lines[idx].strip() != '}':
    idx -= 1
lines.insert(idx, '  services.k3s.extraFlags = lib.mkForce [ "--invalid-flag-xyz" ];\n')
open(path, 'w').writelines(lines)
PYEOF

git -C "$VIGIL_REPO_ROOT" commit -am "os-2g: inject fault"
git -C "$VIGIL_REPO_ROOT" push origin eval-baseline

ssh "${SSH_OPTS[@]}" "root@${TARGET_HOST}" \
  "systemctl start --no-block vigil-auto-reconcile.service"

sleep 1

TIMEOUT=120
ELAPSED=0
while ssh "${SSH_OPTS[@]}" "root@${TARGET_HOST}" \
    "systemctl is-active vigil-auto-reconcile.service" 2>/dev/null | grep -q "^active"; do
  sleep 2
  ELAPSED=$((ELAPSED + 2))
  if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo "inject.sh: os-2g timeout waiting for auto-reconciler" >&2
    break
  fi
done

ssh "${SSH_OPTS[@]}" "root@${TARGET_HOST}" \
  "! systemctl is-active --quiet k3s" || true

echo "inject.sh: os-2g seed=${SEED} complete"
