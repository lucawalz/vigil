#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"
: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
ORIGINAL_REPLICAS=1

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment "${DEPLOYMENT}" \
  --replicas="${ORIGINAL_REPLICAS}" \
  -n "${NAMESPACE}"

git -C "$VIGIL_REPO_ROOT" fetch origin
git -C "$VIGIL_REPO_ROOT" checkout chore/eval-cluster-baseline
git -C "$VIGIL_REPO_ROOT" reset --hard origin/main
git -C "$VIGIL_REPO_ROOT" push --force-with-lease origin chore/eval-cluster-baseline

flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"
flux reconcile kustomization flux-system -n flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"

echo "reset.sh: deceptive-2 seed=${SEED} complete"
