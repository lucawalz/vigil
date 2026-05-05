#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" patch "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type='json' \
  -p='[{"op":"remove","path":"/spec/template/spec/containers/0/env"}]' \
  2>/dev/null || true

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=120s

flux --kubeconfig "$EVAL_RUNNER_KUBECONFIG" resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: k8s-2 seed=${SEED} — cluster at baseline"
