# Security policy

vigil handles cluster and cloud credentials (a Hetzner Cloud API token, a GitHub token, kubeconfig and cluster credentials) alongside LLM provider credentials (Anthropic or Ollama API keys). These are read from environment variables. The orchestrator webhook secret is generated per cluster at provisioning time. No plaintext secret is committed.

## Reporting a vulnerability

Report a suspected vulnerability privately through the "Report a vulnerability" form under the repository's Security tab, rather than opening a public issue. A maintainer will respond there.

## Supported versions

| Version  | Supported                                                                |
| -------- | ------------------------------------------------------------------------ |
| `main`   | Receives fixes                                                           |
| `v1.0.0` | Archived evaluation release, kept unchanged for reproducibility          |
