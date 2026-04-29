#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="postgresql"
BAD_IMAGE="bitnami/postgresql:bogus-tag-v0"

kubectl set image \
  "statefulset/${STATEFULSET}" \
  "postgresql=${BAD_IMAGE}" \
  -n "${NAMESPACE}"

echo "inject.sh: pg-1 seed=${SEED} complete"
