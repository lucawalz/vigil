# Security policy

vigil handles cluster and cloud credentials (a Hetzner Cloud API token, GitHub App private keys or a GitHub token, kubeconfig and cluster credentials) alongside LLM provider credentials (Anthropic or Ollama API keys). These are read from environment variables; the GitHub App private keys are read from files whose paths come from environment variables. The orchestrator webhook secret is generated per cluster at provisioning time. No plaintext secret is committed.

## Reporting a vulnerability

Report a suspected vulnerability privately through the "Report a vulnerability" form in the repository's Security tab, at `https://github.com/lucawalz/vigil/security/advisories/new`. Do not open a public issue, pull request or discussion for a suspected vulnerability.

A useful report names the affected version or commit, describes the impact, and includes steps or a proof of concept that reproduce the problem.

## Response

- Acknowledgement within 7 days of the report.
- Coordinated disclosure within 90 days of the report, earlier when a fix ships sooner.
- The reporter is credited in the published advisory unless they ask otherwise.
- The discussion stays in the private advisory, which is published with the affected and fixed versions once a fix is released.

## Supported versions

| Version  | Supported                                                                |
| -------- | ------------------------------------------------------------------------ |
| `main`   | Receives fixes                                                           |
| `v2.x`   | Latest release; fixes ship in a patch release                            |
| `v1.1.0` | Superseded by `v2.0.0`                                                   |
| `v1.0.0` | Archived evaluation release, kept unchanged for reproducibility          |
