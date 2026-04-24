#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"

kubectl delete secret vigil-app-pullsecret -n "${NAMESPACE}" 2>/dev/null || true

echo "inject.sh: boundary-1 seed=${SEED} complete"
