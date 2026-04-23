#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-1}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
CONFIG_DIR="/opt/nixos-config/hosts/hetzner-worker-1"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "printf '{ lib, ... }:\n{\n  services.k3s.enable = lib.mkForce false;\n}\n' > ${CONFIG_DIR}/bad-module.nix"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "grep -q 'bad-module.nix' ${CONFIG_DIR}/default.nix || sed -i 's|imports = \[|imports = [\n    ./bad-module.nix|' ${CONFIG_DIR}/default.nix"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch --flake /opt/nixos-config#hetzner-worker-1"

echo "inject.sh: os-1 seed=${SEED} complete"
