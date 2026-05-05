#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
PVC="vigil-app-data"
DEPLOYMENT="vigil-app"
MANIFEST_DIR="$(cd "$(dirname "$0")" && pwd)/manifests"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment "${DEPLOYMENT}" -n "${NAMESPACE}" --replicas=0
kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" wait --for=delete pod -n "${NAMESPACE}" -l app=vigil-app --timeout=60s 2>/dev/null || true

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" delete pvc "${PVC}" -n "${NAMESPACE}" --ignore-not-found --wait=true --timeout=60s

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f "${MANIFEST_DIR}/" -n "${NAMESPACE}"
kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment "${DEPLOYMENT}" -n "${NAMESPACE}" --replicas=1
kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=180s

flux --kubeconfig "$EVAL_RUNNER_KUBECONFIG" resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: k8s-5 seed=${SEED} — cluster at baseline"
