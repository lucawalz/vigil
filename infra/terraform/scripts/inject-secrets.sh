#!/usr/bin/env bash
set -euo pipefail

root="$(mktemp -d)"
trap 'rm -rf "${root}"' EXIT

if [[ -n "${K3S_TOKEN:-}" ]]; then
  install -d -m 755 "${root}/etc/k3s"
  printf '%s' "${K3S_TOKEN}" > "${root}/etc/k3s/token"
  chmod 0400 "${root}/etc/k3s/token"
fi

trap - EXIT
echo "${root}"
