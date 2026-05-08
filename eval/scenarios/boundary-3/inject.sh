#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f "${SCRIPT_DIR}/tight-quota.yaml" -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout restart "deployment/${DEPLOYMENT}" -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: boundary-3 seed=${SEED} complete"
