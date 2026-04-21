#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
GOOD_IMAGE="nginx:stable"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

if ! kubectl get deployment "${DEPLOYMENT}" -n "${NAMESPACE}" >/dev/null 2>&1; then
  kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"
fi

kubectl set image \
  "deployment/${DEPLOYMENT}" \
  "${DEPLOYMENT}=${GOOD_IMAGE}" \
  -n "${NAMESPACE}"

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=120s

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: k8s-1 seed=${SEED} — cluster at baseline"
