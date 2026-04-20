#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
PVC="vigil-app-data"
DEPLOYMENT="vigil-app"

kubectl delete pvc "${PVC}" -n "${NAMESPACE}" --ignore-not-found --wait=false
kubectl delete pod -n "${NAMESPACE}" -l app=vigil-app --ignore-not-found --wait=false

cat <<'EOF' | kubectl apply -n "${NAMESPACE}" -f -
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

kubectl rollout restart "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" || true
kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: k8s-5 seed=${SEED} complete"
