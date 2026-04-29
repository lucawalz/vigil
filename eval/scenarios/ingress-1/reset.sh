#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
SERVICE="vigil-app-svc"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl wait --for=condition=Available \
  "service/${SERVICE}" \
  -n "${NAMESPACE}" \
  --timeout=30s 2>/dev/null || true

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: ingress-1 seed=${SEED} — cluster at baseline"
