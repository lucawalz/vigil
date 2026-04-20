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

HETZNER_HOST_KEYS_DIR="${HETZNER_HOST_KEYS_DIR:-${HOME}/.ssh/hetzner-host-keys}"
STABLE_KEY="${HETZNER_HOST_KEYS_DIR}/${ROLE}_ed25519"

install -d -m 700 "${root}/etc/ssh"
if [[ -r "${STABLE_KEY}" && -r "${STABLE_KEY}.pub" ]]; then
  install -m 600 "${STABLE_KEY}"     "${root}/etc/ssh/ssh_host_ed25519_key"
  install -m 644 "${STABLE_KEY}.pub" "${root}/etc/ssh/ssh_host_ed25519_key.pub"
else
  ssh-keygen -t ed25519 -N "" \
    -f "${root}/etc/ssh/ssh_host_ed25519_key" \
    -C "root@${ROLE}" >&2
  echo "warning: no stable host key at ${STABLE_KEY}; agenix decryption will fail unless this fresh key's pubkey is added to infra/nixos/secrets/secrets.nix" >&2
fi

install -d -m 700 "${root}/etc/sops/age"
install -m 600 "${SOPS_AGE_KEY_FILE}" "${root}/etc/sops/age/keys.txt"

# Disable EXIT trap so the temp dir survives for nixos-anywhere to read.
trap - EXIT
echo "${root}"
