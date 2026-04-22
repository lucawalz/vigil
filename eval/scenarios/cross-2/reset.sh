#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=120s

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: cross-2 seed=${SEED} — cluster at baseline"
