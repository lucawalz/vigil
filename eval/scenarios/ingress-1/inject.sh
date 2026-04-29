#!/usr/bin/env bash
set -euo pipefail

SEED="${1:-1}"
NAMESPACE="default"
SERVICE="vigil-app-svc"

kubectl delete service "${SERVICE}" -n "${NAMESPACE}" --ignore-not-found=true

echo "inject.sh: ingress-1 seed=${SEED} complete"
