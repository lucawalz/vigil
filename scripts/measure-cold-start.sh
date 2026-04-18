#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "usage: $0 <host> <flake-directory>" >&2
  echo "example: $0 worker-1 ~/nixos-homelab" >&2
  exit 1
fi

HOST="$1"
FLAKE=$(cd "$2" && pwd)
if [ ! -f "${FLAKE}/flake.nix" ]; then
  echo "error: no flake.nix in ${FLAKE}" >&2
  exit 1
fi

nixos_rebuild() {
  if command -v nixos-rebuild >/dev/null 2>&1; then
    nixos-rebuild "$@"
  elif command -v nix >/dev/null 2>&1; then
    nix run nixpkgs#nixos-rebuild -- "$@"
  else
    echo "error: nixos-rebuild not found and nix is not on PATH" >&2
    exit 1
  fi
}

SAMPLES=3
READY_TIMEOUT="${MEASURE_READY_TIMEOUT:-600}"
COOLDOWN="${MEASURE_COOLDOWN_SEC:-20}"
times=()

use_local_kubectl=0
if command -v kubectl >/dev/null 2>&1 && kubectl get node "${HOST}" -o name >/dev/null 2>&1; then
  use_local_kubectl=1
fi

node_ready_status() {
  if [ "$use_local_kubectl" = 1 ]; then
    kubectl get node "${HOST}" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null | tr -d '[:space:]' || true
  else
    ssh "root@$HOST" "kubectl get node '${HOST}' -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" 2>/dev/null | tr -d '[:space:]' || true
  fi
}

for ((i = 1; i <= SAMPLES; i++)); do
  t_start=$(date +%s)
  if ! nixos_rebuild test --flake "${FLAKE}#${HOST}" --build-host "root@${HOST}" --target-host "root@${HOST}" --sudo; then
    echo "error: nixos-rebuild test failed for ${HOST}" >&2
    exit 1
  fi
  ssh "root@${HOST}" "systemctl stop rollback-gate.timer rollback-gate.service 2>/dev/null || true"
  echo "sample ${i}/${SAMPLES}: waiting for node ${HOST} Ready (timeout ${READY_TIMEOUT}s)..." >&2
  ready=0
  max_polls=$((READY_TIMEOUT / 2))
  for ((poll = 0; poll < max_polls; poll++)); do
    status=$(node_ready_status)
    if [ "$status" = "True" ]; then
      ready=1
      break
    fi
    if ((poll > 0 && poll % 15 == 0)); then
      echo "  still waiting (~$((poll * 2))s, last status: '${status:-empty}')..." >&2
    fi
    sleep 2
  done
  if [ "$ready" != 1 ]; then
    echo "error: ${HOST} not Ready within ${READY_TIMEOUT}s after rebuild (sample ${i})" >&2
    if [ "$use_local_kubectl" = 1 ]; then
      kubectl get node "${HOST}" -o wide 2>&1 || true
    else
      ssh "root@$HOST" "kubectl get node '${HOST}' -o wide 2>&1; kubectl get node -o wide 2>&1" >&2 || true
    fi
    exit 1
  fi
  t_end=$(date +%s)
  times+=($((t_end - t_start)))
  if ((i < SAMPLES)); then
    echo "waiting ${COOLDOWN}s before next sample..." >&2
    sleep "$COOLDOWN"
  fi
done

max=0
for t in "${times[@]}"; do
  if ((t > max)); then
    max=$t
  fi
done
recommended=$(( (max * 3 + 1) / 2 ))

ssh "root@${HOST}" "systemctl start rollback-gate.timer 2>/dev/null || true"

echo "Samples: ${times[*]}"
echo "Max: ${max}s"
echo "OnActiveSec (ceil(max*1.5)): ${recommended}s"
