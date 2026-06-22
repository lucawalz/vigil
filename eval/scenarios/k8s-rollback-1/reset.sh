#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" \
  delete resourcequota tight-quota -n default --ignore-not-found

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment vigil-app \
  --replicas=1 -n default
kubectl rollout status deployment/vigil-app -n default --timeout=60s \
  --kubeconfig "$EVAL_RUNNER_KUBECONFIG" 2>&1 || true

echo "reset.sh: k8s-rollback-1 seed=${SEED} - cluster at baseline"
