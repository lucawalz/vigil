#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" delete secret vigil-app-pullsecret -n "${NAMESPACE}" 2>/dev/null || true

echo "inject.sh: boundary-1 seed=${SEED} complete"
