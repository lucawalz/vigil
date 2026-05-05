#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" patch "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"4Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"4Mi"}]'

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: k8s-3 seed=${SEED} complete"
