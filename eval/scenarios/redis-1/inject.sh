#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="redis-master"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" set resources \
  "statefulset/${STATEFULSET}" \
  -c redis \
  --limits=memory=10Mi \
  -n "${NAMESPACE}"

echo "inject.sh: redis-1 seed=${SEED} complete"
