#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
STATEFULSET="redis-master"

kubectl set resources \
  "statefulset/${STATEFULSET}" \
  -c redis \
  --limits=memory=10Mi \
  -n "${NAMESPACE}"

echo "inject.sh: redis-1 seed=${SEED} complete"
