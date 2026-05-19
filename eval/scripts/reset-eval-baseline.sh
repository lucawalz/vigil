#!/usr/bin/env bash
set -euo pipefail

: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

REPO_ROOT="${VIGIL_REPO_ROOT:-/root/vigil}"

git -C "$REPO_ROOT" fetch origin
git push --force origin "origin/main:eval-baseline"
flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG" \
  || echo "reset-eval-baseline: flux source reconcile failed, continuing" >&2

echo "reset-eval-baseline: eval-baseline reset to origin/main" >&2
