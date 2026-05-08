#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
CONFIGMAP="vigil-app-config"
DEPLOYMENT="vigil-app"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" delete configmap "${CONFIGMAP}" -n "${NAMESPACE}" --ignore-not-found

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout restart "deployment/${DEPLOYMENT}" -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: boundary-2 seed=${SEED} complete"
