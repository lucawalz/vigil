#!/usr/bin/env bash
set -euo pipefail

: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
MANIFEST="$VIGIL_REPO_ROOT/infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"

git -C "$VIGIL_REPO_ROOT" checkout -- "$MANIFEST" 2>/dev/null || true

sed -i '/limits:/,/^[^ ]/ s|memory: "128Mi"|memory: "4Mi"|' "$MANIFEST"

git -C "$VIGIL_REPO_ROOT" commit -am "k8s-3g: inject fault"
git -C "$VIGIL_REPO_ROOT" push origin HEAD:chore/eval-cluster-baseline
flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"
flux reconcile kustomization flux-system -n flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG" || true
flux reconcile kustomization cluster-apps -n flux-system --timeout=120s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"

echo "inject.sh: k8s-3g seed=${SEED} complete"
