#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
DEPLOYMENT="vigil-app"

kubectl patch "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/resources/limits/memory","value":"4Mi"},{"op":"replace","path":"/spec/template/spec/containers/0/resources/requests/memory","value":"4Mi"}]'

kubectl rollout status "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" --timeout=30s 2>&1 || true

echo "inject.sh: cross-2 seed=${SEED} complete"
