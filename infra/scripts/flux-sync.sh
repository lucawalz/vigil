#!/usr/bin/env bash
set -euo pipefail

USAGE="Usage: flux-sync.sh <repo-url> <branch> <path>"
REPO_URL="${1:?$USAGE}"
BRANCH="${2:?$USAGE}"
SYNC_PATH="${3:?$USAGE}"
TIMEOUT=10m
SOURCE_INTERVAL=1m
SYNC_INTERVAL=10m
CONTROL_PLANE_NODE='{"spec":{"template":{"spec":{"nodeSelector":{"node-role.kubernetes.io/control-plane":"true"}}}}}'

flux install --timeout="$TIMEOUT"
kubectl -n flux-system patch deployment source-controller --type merge -p "$CONTROL_PLANE_NODE"
flux create source git flux-system --url="$REPO_URL" --branch="$BRANCH" \
  --interval="$SOURCE_INTERVAL" --timeout="$TIMEOUT"
flux create kustomization flux-system --source=GitRepository/flux-system --path="$SYNC_PATH" \
  --prune=true --interval="$SYNC_INTERVAL" --timeout="$TIMEOUT"
