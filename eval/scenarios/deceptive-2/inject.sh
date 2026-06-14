#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"
: "${VIGIL_REPO_ROOT:?VIGIL_REPO_ROOT must be set}"

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"
CONTAINER="vigil-app"
DECLARED_IMAGE="nginx:declared-missing"
LIVE_IMAGE="nginx:live-missing"
MANIFEST="$VIGIL_REPO_ROOT/infra/overlays/hetzner/kubernetes/clusters/hetzner/apps/vigil-app.yaml"

flux suspend kustomization cluster-apps -n flux-system --kubeconfig "$EVAL_RUNNER_KUBECONFIG"

git -C "$VIGIL_REPO_ROOT" checkout -- "$MANIFEST" 2>/dev/null || true

sed -i "s|image: nginx:stable|image: ${DECLARED_IMAGE}|" "$MANIFEST"

git -C "$VIGIL_REPO_ROOT" \
  -c user.name="eval-harness" \
  -c user.email="eval@vigil.local" \
  commit -am "deceptive-2: inject fault"

(cd "$VIGIL_REPO_ROOT" && git push origin HEAD:chore/eval-cluster-baseline)

flux reconcile source git flux-system --timeout=60s --kubeconfig "$EVAL_RUNNER_KUBECONFIG" || true

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" set image \
  "deployment/${DEPLOYMENT}" "${CONTAINER}=${LIVE_IMAGE}" \
  -n "${NAMESPACE}"

kubectl rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout=30s \
  --kubeconfig "$EVAL_RUNNER_KUBECONFIG" 2>&1 || true

echo "inject.sh: deceptive-2 seed=${SEED} complete"
