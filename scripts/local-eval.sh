#!/usr/bin/env bash
set -euo pipefail

REQUIRED_ENV_VARS=(
  TF_VAR_hcloud_token
  TF_VAR_github_token
  TF_VAR_vigil_webhook_secret
  TF_VAR_llm_api_key
  TF_VAR_llm_base_url
  TF_VAR_llm_model_name
)

for var in "${REQUIRED_ENV_VARS[@]}"; do
  if [[ -z "${!var:-}" ]]; then
    echo "error: $var is not set (load .envrc via direnv)" >&2
    exit 1
  fi
done

AGE_KEY_FILE="$HOME/.config/sops/age/hetzner-eval-keys.txt"
if [[ ! -f "$AGE_KEY_FILE" ]]; then
  echo "error: age key not found at $AGE_KEY_FILE" >&2
  exit 1
fi

SECRETS_FILE=$(mktemp /tmp/vigil-local-eval-secrets.XXXXXX)
trap 'rm -f "$SECRETS_FILE"' EXIT

cat > "$SECRETS_FILE" <<EOF
TF_VAR_HCLOUD_TOKEN=${TF_VAR_hcloud_token}
TF_VAR_GITHUB_TOKEN=${TF_VAR_github_token}
TF_VAR_VIGIL_WEBHOOK_SECRET=${TF_VAR_vigil_webhook_secret}
TF_VAR_LLM_API_KEY=${TF_VAR_llm_api_key}
TF_VAR_LLM_BASE_URL=${TF_VAR_llm_base_url}
TF_VAR_LLM_MODEL_NAME=${TF_VAR_llm_model_name}
SOPS_AGE_KEY=$(grep '^AGE-SECRET-KEY-' "$AGE_KEY_FILE")
EOF
chmod 600 "$SECRETS_FILE"

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
MODEL="${TF_VAR_llm_model_name}"

PAYLOAD_FILE=$(mktemp /tmp/vigil-local-eval-payload.XXXXXX.json)
trap 'rm -f "$SECRETS_FILE" "$PAYLOAD_FILE"' EXIT

cat > "$PAYLOAD_FILE" <<EOF
{
  "inputs": {
    "vigil_branch": "${VIGIL_BRANCH:-$CURRENT_BRANCH}",
    "seed": "${SEED:-1}",
    "concurrency": "${CONCURRENCY:-1}",
    "model": "$MODEL"
  }
}
EOF

mkdir -p .artifacts

act workflow_dispatch \
  -W .github/workflows/eval-campaign.yml \
  -e "$PAYLOAD_FILE" \
  --secret-file "$SECRETS_FILE" \
  --env LOCAL_RUN=1 \
  --artifact-server-path "$PWD/.artifacts" \
  -P ubuntu-latest=catthehacker/ubuntu:full-latest \
  "$@"
