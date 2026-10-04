#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:?Usage: agent-exec.sh <command>}"
: "${VIGIL_EVAL_TARGET:?VIGIL_EVAL_TARGET must be set}"

case "$VIGIL_EVAL_TARGET" in
  hetzner)
    : "${AGENT_IP:?AGENT_IP must be set for the hetzner target}"
    exec ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
      -o ServerAliveInterval=30 -o ServerAliveCountMax=10 \
      "root@$AGENT_IP" -- "set -a; . /etc/vigil/env; set +a; cd /root/vigil && $COMMAND"
    ;;
  runner)
    : "${LAB_ENV:?LAB_ENV must be set for the runner target}"
    exec bash -c "set -a; . \"\$LAB_ENV\"; set +a; export PATH=\"\$PWD/.venv/bin:\$PATH\"; $COMMAND"
    ;;
  *)
    echo "agent-exec: unsupported VIGIL_EVAL_TARGET $VIGIL_EVAL_TARGET" >&2
    exit 1
    ;;
esac
