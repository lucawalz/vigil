#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${1:-${EVAL_RUNNER_KUBECONFIG:-}}"

: "${KUBECONFIG_PATH:?Usage: wait-flux-ready.sh <kubeconfig-path> OR set EVAL_RUNNER_KUBECONFIG}"

DEADLINE_S="${WAIT_FLUX_READY_DEADLINE_S:-900}"
POLL_INTERVAL_S="${WAIT_FLUX_READY_POLL_S:-15}"

deadline=$(($(date +%s) + DEADLINE_S))

while [ "$(date +%s)" -lt "$deadline" ]; do
  echo "--- $(date -u +%H:%M:%SZ) ---"
  kubectl --kubeconfig "$KUBECONFIG_PATH" get kustomization \
    cluster-infrastructure cluster-apps \
    -n flux-system \
    --request-timeout=15s \
    -o custom-columns='NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,REASON:.status.conditions[?(@.type=="Ready")].reason' \
    --no-headers 2>&1 || echo "(kubectl error - cluster not reachable yet)"
  kubectl --kubeconfig "$KUBECONFIG_PATH" get helmrelease \
    -A \
    --request-timeout=15s \
    -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,READY:.status.conditions[?(@.type=="Ready")].status,REASON:.status.conditions[?(@.type=="Ready")].reason' \
    --no-headers 2>/dev/null || true

  KS_READY=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get kustomization \
    cluster-infrastructure cluster-apps \
    -n flux-system \
    --request-timeout=15s \
    -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  KS_COUNT=$(echo "$KS_READY" | tr ' ' '\n' | grep -c '^True$' || true)

  HR_READY=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get helmrelease \
    postgresql redis \
    -n default \
    --request-timeout=15s \
    -o jsonpath='{.items[*].status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "")
  HR_COUNT=$(echo "$HR_READY" | tr ' ' '\n' | grep -c '^True$' || true)

  if [ "$KS_COUNT" -eq 2 ] && [ "$HR_COUNT" -eq 2 ]; then
    echo "all flux kustomizations and storage helmreleases ready"
    exit 0
  fi

  sleep "$POLL_INTERVAL_S"
done

echo "wait-flux-ready: timeout after ${DEADLINE_S}s - cluster not ready" >&2
kubectl --kubeconfig "$KUBECONFIG_PATH" get kustomization -n flux-system --request-timeout=15s 2>&1 || true
kubectl --kubeconfig "$KUBECONFIG_PATH" get helmrelease -A --request-timeout=15s 2>&1 || true
exit 1
