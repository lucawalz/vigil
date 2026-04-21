#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
PVC="vigil-app-data"
DEPLOYMENT="vigil-app"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl delete pod -n "${NAMESPACE}" -l app=vigil-app --ignore-not-found --wait=false
kubectl wait --for=delete pod -n "${NAMESPACE}" -l app=vigil-app --timeout=60s 2>/dev/null || true

kubectl delete pvc "${PVC}" -n "${NAMESPACE}" --ignore-not-found --wait=true --timeout=60s

kubectl apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl rollout restart "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" || true
kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=180s

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: k8s-5 seed=${SEED} — cluster at baseline"
