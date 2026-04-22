#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
TARGET_HOST="${TARGET_HOST:-hetzner-worker-2}"
SSH_KEY="${SSH_KEY_PATH:-$HOME/.ssh/id_ed25519}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "systemctl start k3s.service || true && printf '{ }\n' > /opt/nixos-config/hosts/hetzner-worker-2/bad-module.nix"

ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no "root@${TARGET_HOST}" \
  "nixos-rebuild switch --flake /opt/nixos-config#hetzner-worker-2"

kubectl delete deployment "${DEPLOYMENT}" -n "${NAMESPACE}" --ignore-not-found=true
kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=120s

echo "reset.sh: cross-2 seed=${SEED} — cluster at baseline"
