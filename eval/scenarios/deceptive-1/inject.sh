#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
MISSING_CM="nonexistent-config"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" patch deployment "${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type=strategic \
  --patch "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"${DEPLOYMENT}\",\"envFrom\":[{\"configMapRef\":{\"name\":\"${MISSING_CM}\"}}]}]}}}}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: deceptive-1 seed=${SEED} complete"
