#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"
: "${EVAL_RUNNER_KUBECONFIG:?EVAL_RUNNER_KUBECONFIG must be set}"

SEED="${1:-1}"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -f - <<'EOF'
apiVersion: v1
kind: ResourceQuota
metadata:
  name: tight-quota
  namespace: default
spec:
  hard:
    requests.memory: "32Mi"
    limits.memory: "32Mi"
EOF

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment vigil-app \
  --replicas=0 -n default
kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment vigil-app \
  --replicas=1 -n default

kubectl rollout status deployment/vigil-app -n default --timeout=30s \
  --kubeconfig "$EVAL_RUNNER_KUBECONFIG" 2>&1 || true

echo "inject.sh: live-quota-injected seed=${SEED} complete"
