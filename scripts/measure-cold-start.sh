#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <host>" >&2
  exit 1
fi

HOST="$1"
SAMPLES=3
times=()

for ((i = 1; i <= SAMPLES; i++)); do
  t_start=$(date +%s)
  if ! ssh "root@$HOST" 'sudo nixos-rebuild test 2>/dev/null'; then
    echo "error: nixos-rebuild test failed on ${HOST}" >&2
    exit 1
  fi
  while true; do
    status=$(
      ssh "root@$HOST" "kubectl get node \$(hostname) -o jsonpath='{.status.conditions[?(@.type==\"Ready\")].status}'" 2>/dev/null || true
    )
    if [ "$status" = "True" ]; then
      break
    fi
    sleep 2
  done
  t_end=$(date +%s)
  times+=($((t_end - t_start)))
done

max=0
for t in "${times[@]}"; do
  if ((t > max)); then
    max=$t
  fi
done
recommended=$(( (max * 3 + 1) / 2 ))

echo "Samples: ${times[*]}"
echo "Max: ${max}s"
echo "OnActiveSec (ceil(max*1.5)): ${recommended}s"
