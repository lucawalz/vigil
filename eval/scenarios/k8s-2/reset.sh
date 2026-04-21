#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl patch "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/containers/0/env"}]' \
  2>/dev/null || true

kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=120s

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: k8s-2 seed=${SEED} — cluster at baseline"
