#!/usr/bin/env bash
set -euo pipefail

: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"
: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"
MANIFEST="$VIGIL_REPO_ROOT/infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"

git -C "$VIGIL_REPO_ROOT" checkout -- "$MANIFEST" 2>/dev/null || true

sed -i '/limits:/,/^[^ ]/ s|memory: "128Mi"|memory: "4Mi"|' "$MANIFEST"

git -C "$VIGIL_REPO_ROOT" commit -am "k8s-rollback-1: inject fault"
git -C "$VIGIL_REPO_ROOT" push origin HEAD:chore/eval-cluster-baseline

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f - <<'EOF'
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tight-quota
  namespace: default
spec:
  hard:
    limits.memory: "64Mi"
EOF

flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG"
flux reconcile kustomization flux-system -n flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG" || true
flux reconcile kustomization cluster-apps -n flux-system --timeout=120s --kubeconfig "$EVAL_RUNNER_KUBECONFIG" || true

echo "inject.sh: k8s-rollback-1 seed=${SEED} complete"
