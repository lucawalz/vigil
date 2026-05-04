#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
SERVICE="vigil-app-svc"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl get service "${SERVICE}" -n "${NAMESPACE}" --no-headers \
  || { echo "reset.sh: service ${SERVICE} not found after apply"; exit 1; }

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: ingress-1 seed=${SEED} — cluster at baseline"
