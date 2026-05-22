#!/usr/bin/env bash
set -euo pipefail

: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

REPO_ROOT="${VIGIL_REPO_ROOT:-/root/vigil}"
SSH_KEY="${SSH_KEY_PATH:-/root/.ssh/id_ed25519}"
SSH_USER="${SSH_USER:-root}"

EVAL_BRANCH="chore/eval-cluster-baseline"

git -C "$REPO_ROOT" fetch origin
git -C "$REPO_ROOT" reset --hard origin/main
git -C "$REPO_ROOT" push --force origin HEAD:"$EVAL_BRANCH"

flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG" \
  || echo "reset-eval-baseline: flux source reconcile failed, continuing" >&2

for host in hetzner-worker-1 hetzner-worker-2; do
  ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    "$SSH_USER@$host" \
    "git -C /opt/nixos-config fetch origin && git -C /opt/nixos-config reset --hard origin/$EVAL_BRANCH" \
    || echo "reset-eval-baseline: worker tree reset failed on $host, continuing" >&2
done

echo "reset-eval-baseline: $EVAL_BRANCH reset to origin/main" >&2
