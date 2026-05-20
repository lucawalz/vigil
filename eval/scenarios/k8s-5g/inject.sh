#!/usr/bin/env bash
set -euo pipefail

: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
MANIFEST="$VIGIL_REPO_ROOT/infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"

git -C "$VIGIL_REPO_ROOT" checkout -- "$MANIFEST" 2>/dev/null || true

python3 -c "
import yaml, sys
with open('$MANIFEST') as f:
    obj = yaml.safe_load(f)
obj['spec']['selector']['matchLabels']['app'] = 'vigil-app-typo'
with open('$MANIFEST', 'w') as f:
    yaml.dump(obj, f, default_flow_style=False, sort_keys=False)
"

git -C "$VIGIL_REPO_ROOT" commit -am "k8s-5g: inject fault"
git -C "$VIGIL_REPO_ROOT" push origin chore/eval-cluster-baseline
flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"
flux reconcile kustomization flux-system -n flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"
kubectl rollout status deployment/vigil-app -n default --timeout=30s \
  --kubeconfig "$EVAL_RUNNER_KUBECONFIG" 2>&1 || true

echo "inject.sh: k8s-5g seed=${SEED} complete"
