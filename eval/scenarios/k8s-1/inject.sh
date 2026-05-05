#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
BAD_IMAGE="nginx:bad-tag-v9"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" set image \
  "deployment/${DEPLOYMENT}" \
  "${DEPLOYMENT}=${BAD_IMAGE}" \
  -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: k8s-1 seed=${SEED} complete"
