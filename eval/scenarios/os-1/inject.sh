#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
CONFIG_DIR="/etc/nixos"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "printf 'this is not valid nix {\n' > ${CONFIG_DIR}/bad-module.nix"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "grep -q 'bad-module.nix' ${CONFIG_DIR}/configuration.nix || sed -i 's|imports = \[|imports = [\n    ./bad-module.nix|' ${CONFIG_DIR}/configuration.nix"

echo "inject.sh: os-1 seed=${SEED} complete"
