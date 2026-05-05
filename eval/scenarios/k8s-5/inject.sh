#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
PVC="vigil-app-data"
DEPLOYMENT="vigil-app"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" scale deployment "${DEPLOYMENT}" -n "${NAMESPACE}" --replicas=0
kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" wait --for=delete pod -n "${NAMESPACE}" -l app=vigil-app --timeout=60s 2>/dev/null || true

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" delete pvc "${PVC}" -n "${NAMESPACE}" --ignore-not-found --wait=true --timeout=60s

cat <<'EOF' | kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" apply -n "${NAMESPACE}" -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: vigil-app-data
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: does-not-exist
  resources:
    requests:
      storage: 100Mi
EOF

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout restart "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" || true
kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: k8s-5 seed=${SEED} complete"
