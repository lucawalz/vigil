#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
SERVICE="vigil-app-svc"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" get service "${SERVICE}" -n "${NAMESPACE}" --no-headers \
  || echo "reset.sh: service ${SERVICE} not found after apply"

flux --kubeconfig "$EVAL_RUNNER_KUBECONFIG" resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: ingress-1 seed=${SEED} — cluster at baseline"
