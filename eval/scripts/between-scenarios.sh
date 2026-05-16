#!/usr/bin/env bash
set -euo pipefail

: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

PREV_SCENARIO="${1:?Usage: between-scenarios.sh <previous-scenario-id> <group-name>}"
GROUP="${2:?Usage: between-scenarios.sh <previous-scenario-id> <group-name>}"

: "${PREV_RUN_ID:?PREV_RUN_ID must be set}"

REPO_ROOT="${VIGIL_REPO_ROOT:-/root/vigil}"
AGENT_HOST="${AGENT_HOST:-}"
SSH_KEY="${SSH_KEY_PATH:-/root/.ssh/id_ed25519}"
SSH_USER="${SSH_USER:-root}"

echo "between-scenarios: prev=$PREV_SCENARIO group=$GROUP" >&2

RUN_JSON="$REPO_ROOT/eval/runs/${PREV_RUN_ID}.json"
MERGE_SHA=""
if [ -f "$RUN_JSON" ]; then
  MERGE_SHA=$(jq -r '.merge_commit_sha // empty' "$RUN_JSON")
fi
if [ -n "$MERGE_SHA" ]; then
  echo "between-scenarios: step 1/6 — revert K8s commit $MERGE_SHA" >&2
  git -C "$REPO_ROOT" revert --no-edit "$MERGE_SHA" || echo "between-scenarios: revert failed, continuing" >&2
else
  echo "between-scenarios: step 1/6 — no K8s merge commit to revert (skip)" >&2
fi

RESET_SCRIPT="$REPO_ROOT/eval/scenarios/$PREV_SCENARIO/reset.sh"
if [ -x "$RESET_SCRIPT" ]; then
  echo "between-scenarios: step 2/6 — running $RESET_SCRIPT" >&2
  "$RESET_SCRIPT" 1 || echo "between-scenarios: reset.sh exited non-zero, continuing" >&2
else
  echo "between-scenarios: skip step 2/6 — $RESET_SCRIPT not executable" >&2
fi

echo "between-scenarios: step 3/6 — flux force-reconcile" >&2
kubectl --kubeconfig "$EVAL_RUNNER_KUBECONFIG" \
  annotate kustomization flux-system -n flux-system \
  "reconcile.fluxcd.io/requestedAt=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --overwrite || echo "between-scenarios: flux reconcile annotation failed, continuing" >&2

if [ "$GROUP" = "cross" ] || [ "$GROUP" = "os" ]; then
  echo "between-scenarios: step 4/6 — nixos-rebuild switch on workers" >&2
  for host in hetzner-worker-1 hetzner-worker-2; do
    ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      "$SSH_USER@$host" \
      "nixos-rebuild switch --flake /opt/nixos-config#$host" \
      || echo "between-scenarios: nixos-rebuild on $host failed, continuing" >&2
  done
else
  echo "between-scenarios: step 4/6 — skipped (group=$GROUP)" >&2
fi

echo "between-scenarios: step 5/6 — restart vigil-orchestrator" >&2
if [ -n "$AGENT_HOST" ]; then
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SSH_USER@$AGENT_HOST" \
    "systemctl restart vigil-orchestrator.service"
else
  systemctl restart vigil-orchestrator.service \
    || echo "between-scenarios: systemctl restart failed, continuing" >&2
fi

echo "between-scenarios: step 6/6 — health gate" >&2
HEALTH_GATE="$REPO_ROOT/eval/scripts/health-gate.sh"
exec "$HEALTH_GATE" "$EVAL_RUNNER_KUBECONFIG"
