#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
CONFIGMAP="vigil-app-config"
DEPLOYMENT="vigil-app"

kubectl delete configmap "${CONFIGMAP}" -n "${NAMESPACE}" --ignore-not-found

kubectl rollout restart "deployment/${DEPLOYMENT}" -n "${NAMESPACE}"

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: k8s-4 seed=${SEED} complete"
