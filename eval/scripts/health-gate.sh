#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${1:-${EVAL_RUNNER_KUBECONFIG:-}}"

: "${KUBECONFIG_PATH:?Usage: health-gate.sh <kubeconfig-path> OR set EVAL_RUNNER_KUBECONFIG}"

DEADLINE_S=120
POLL_INTERVAL_S=5
NAMESPACE="default"
DEPLOYMENT="vigil-app"

deadline=$(($(date +%s) + DEADLINE_S))
iteration=0

check_nodes_ready() {
  local statuses
  statuses=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get nodes \
    -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  [ -n "$statuses" ] && ! grep -qv '^True$' <(echo "$statuses" | tr ' ' '\n' | grep -v '^$')
}

check_flux_kustomization_ready() {
  local status
  status=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get kustomization \
    -n flux-system flux-system \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  [ "$status" = "True" ]
}

check_vigil_app_ready() {
  local desired ready
  desired=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get deployment "$DEPLOYMENT" \
    -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "")
  ready=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get deployment "$DEPLOYMENT" \
    -n "$NAMESPACE" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
  [ -n "$desired" ] && [ "$ready" = "$desired" ]
}

while [ "$(date +%s)" -lt "$deadline" ]; do
  iteration=$((iteration + 1))
  if check_nodes_ready && check_flux_kustomization_ready && check_vigil_app_ready; then
    echo "HEALTH_GATE: ok (iteration=$iteration)" >&2
    echo "HEALTH_GATE: ok"
    exit 0
  fi
  echo "health-gate: iteration=$iteration, retrying in ${POLL_INTERVAL_S}s" >&2
  sleep "$POLL_INTERVAL_S"
done

echo "DIRTY_STATE_SKIP" >&2
echo "DIRTY_STATE_SKIP"
exit 2
