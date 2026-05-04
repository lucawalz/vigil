#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="redis-master"

kubectl set resources \
  "statefulset/${STATEFULSET}" \
  -c redis \
  --limits=memory=256Mi \
  --requests=memory=128Mi \
  -n "${NAMESPACE}"

kubectl rollout status "statefulset/${STATEFULSET}" \
  -n "${NAMESPACE}" --timeout=120s

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: redis-1 seed=${SEED} — cluster at baseline"
