#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" patch deployment "${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type=json \
  --patch '[{"op":"remove","path":"/spec/template/spec/containers/0/envFrom"}]' \
  2>/dev/null || true

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=120s 2>/dev/null || true

echo "reset.sh: deceptive-1 seed=${SEED} complete"
