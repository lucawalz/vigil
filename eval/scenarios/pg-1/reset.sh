#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="postgresql"
GOOD_IMAGE="docker.io/bitnami/postgresql:16"

kubectl set image \
  "statefulset/${STATEFULSET}" \
  "postgresql=${GOOD_IMAGE}" \
  -n "${NAMESPACE}"

kubectl rollout status "statefulset/${STATEFULSET}" \
  -n "${NAMESPACE}" --timeout=120s

flux resume kustomization flux-system -n flux-system 2>/dev/null || true

echo "reset.sh: pg-1 seed=${SEED} — cluster at baseline"
