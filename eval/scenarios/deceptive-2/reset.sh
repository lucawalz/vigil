#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"
: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
CONTAINER="vigil-app"
BASELINE_IMAGE="nginx:stable"

git -C "$VIGIL_REPO_ROOT" fetch origin
git -C "$VIGIL_REPO_ROOT" checkout chore/eval-cluster-baseline
git -C "$VIGIL_REPO_ROOT" reset --hard origin/main
git -C "$VIGIL_REPO_ROOT" push --force-with-lease origin chore/eval-cluster-baseline

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" set image \
  "deployment/${DEPLOYMENT}" "${CONTAINER}=${BASELINE_IMAGE}" \
  -n "${NAMESPACE}" || true

flux resume kustomization cluster-apps -n flux-system --kubeconfig "$EVAL_RUNNER_KUBECONFIG" \
  || echo "reset.sh: flux resume cluster-apps failed, continuing" >&2

flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"
flux reconcile kustomization flux-system -n flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"

echo "reset.sh: deceptive-2 seed=${SEED} complete"
