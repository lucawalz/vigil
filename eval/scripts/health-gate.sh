#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${1:-${EVAL_RUNNER_KUBECONFIG:-}}"

: "${KUBECONFIG_PATH:?Usage: health-gate.sh <kubeconfig-path> OR set EVAL_RUNNER_KUBECONFIG}"

DEADLINE_S=600
POLL_INTERVAL_S=5
NAMESPACE="default"
DEPLOYMENT="vigil-app"
ORCHESTRATOR_URL="${VIGIL_ORCHESTRATOR_URL:-http://localhost:9099}"

deadline=$(($(date +%s) + DEADLINE_S))
iteration=0

check_nodes_ready() {
  local statuses filtered
  statuses=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get nodes \
    -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  filtered=$(echo "$statuses" | tr ' ' '\n' | grep -v '^$')
  [ -n "$filtered" ] && ! grep -qv '^True$' <(echo "$filtered")
}

check_cluster_infrastructure_ready() {
  local status
  status=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get kustomization \
    -n flux-system cluster-infrastructure \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  [ "$status" = "True" ]
}

check_flux_kustomization_ready() {
  local status
  status=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get kustomization \
    -n flux-system cluster-apps \
    -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  [ "$status" = "True" ]
}

check_orchestrator_ready() {
  curl -sf "${ORCHESTRATOR_URL}/healthz" > /dev/null 2>&1
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
  failed=()
  check_nodes_ready                  || failed+=("nodes")
  check_cluster_infrastructure_ready || failed+=("cluster-infrastructure")
  check_flux_kustomization_ready     || failed+=("cluster-apps")
  check_vigil_app_ready              || failed+=("vigil-app")
  check_orchestrator_ready           || failed+=("orchestrator")
  if [ ${#failed[@]} -eq 0 ]; then
    echo "HEALTH_GATE: ok (iteration=$iteration)" >&2
    echo "HEALTH_GATE: ok"
    exit 0
  fi
  echo "health-gate: iteration=$iteration, waiting on: ${failed[*]}" >&2
  sleep "$POLL_INTERVAL_S"
done

echo "DIRTY_STATE_SKIP" >&2
echo "DIRTY_STATE_SKIP"
exit 2
