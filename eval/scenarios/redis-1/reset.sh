#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="redis-master"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" set resources \
  "statefulset/${STATEFULSET}" \
  -c redis \
  --limits=memory=256Mi \
  --requests=memory=128Mi \
  -n "${NAMESPACE}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "statefulset/${STATEFULSET}" \
  -n "${NAMESPACE}" --timeout=300s

flux --kubeconfig "$EVAL_RUNNER_KUBECONFIG" resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: redis-1 seed=${SEED} — cluster at baseline"
