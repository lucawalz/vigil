#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
SERVICE="vigil-app-svc"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" delete service "${SERVICE}" -n "${NAMESPACE}" --ignore-not-found=true

echo "inject.sh: ingress-1 seed=${SEED} complete"
