#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${SOPS_AGE_KEY_FILE:-}" ]]; then
  echo "error: SOPS_AGE_KEY_FILE must be exported (path to age private key)" >&2
  exit 1
fi
if [[ ! -r "${SOPS_AGE_KEY_FILE}" ]]; then
  echo "error: SOPS_AGE_KEY_FILE not readable: ${SOPS_AGE_KEY_FILE}" >&2
  exit 1
fi

ROLE="${ROLE:-${1:-unknown}}"

root="$(mktemp -d)"
trap 'rm -rf "${root}"' EXIT

install -d -m 700 "${root}/etc/ssh"
ssh-keygen -t ed25519 -N "" \
  -f "${root}/etc/ssh/ssh_host_ed25519_key" \
  -C "root@${ROLE}" >&2

install -d -m 700 "${root}/etc/sops/age"
install -m 600 "${SOPS_AGE_KEY_FILE}" "${root}/etc/sops/age/keys.txt"

# Disable EXIT trap so the temp dir survives for nixos-anywhere to read.
trap - EXIT
echo "${root}"
