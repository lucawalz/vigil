# Security policy

vigil handles cluster and cloud credentials (a Hetzner Cloud API token, a GitHub token, kubeconfig and cluster credentials, and a SOPS age key) alongside LLM provider credentials (Anthropic or Ollama API keys). These are read from environment variables. Encrypted secrets that live in the repository use SOPS with age. No plaintext secret is committed.

## Reporting a vulnerability

Report a suspected vulnerability privately through the "Report a vulnerability" form under the repository's Security tab, rather than opening a public issue. A maintainer will respond there.

## Supported versions

Only the `main` branch is maintained.
