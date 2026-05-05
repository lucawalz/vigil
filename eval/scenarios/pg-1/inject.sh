#!/usr/bin/env bash
set -euo pipefail

: "${FAULT_INJECTION_KUBECONFIG:?FAULT_INJECTION_KUBECONFIG must be set}"

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="postgresql"
BAD_IMAGE="bitnami/postgresql:bogus-tag-v0"

kubectl --kubeconfig "$FAULT_INJECTION_KUBECONFIG" set image \
  "statefulset/${STATEFULSET}" \
  "postgresql=${BAD_IMAGE}" \
  -n "${NAMESPACE}"

echo "inject.sh: pg-1 seed=${SEED} complete"
