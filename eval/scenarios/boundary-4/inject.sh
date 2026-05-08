#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f "${SCRIPT_DIR}/deny-egress-policy.yaml" -n "${NAMESPACE}"

echo "inject.sh: boundary-4 seed=${SEED} complete"
