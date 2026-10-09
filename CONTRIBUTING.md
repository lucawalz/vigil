# Contributing to vigil

Participation in this project follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## Prerequisites

- Python 3.12 with [uv](https://docs.astral.sh/uv/)
- Go 1.26
- golangci-lint 2.11
- Terraform 1.14
- shellcheck

The Nix development shell (`nix develop`) provides this toolchain. Nix is optional for local checks, where only `make nix-check` and `make vendor-hash` use it, and required for provisioning the eval cluster, which installs Flux through it, and for the local lab (`nix run ./infra/nixos#lab`). Packer builds the NixOS host snapshots and is only needed for work on [`infra/packer/`](infra/packer/).

## Setup and checks

```bash
make setup
make ci
```

`make setup` installs every Python workspace package. `make ci`, which plain `make` also runs, mirrors CI: lint, lockfile check, type check, tests, Go builds, vulnerability scan, Terraform validation and workflow lint. Single targets such as `make lint`, `make test` and `make typecheck` run one part. `make fmt` formats Python, Go and Terraform files.

After changing any `mcp-servers/*/go.mod` or `go.sum`, run `make vendor-hash` and commit the updated `infra/nixos/pkgs/mcp-servers.nix`; the `nix-vendor-hash` CI job fails otherwise.

## Running the orchestrator locally

The orchestrator starts the four MCP servers as subprocesses, so their binaries must be on `PATH`:

```bash
for m in mcp-servers/*/; do (cd "$m" && go install .); done
```

| Variable | Purpose |
|----------|---------|
| `LLM_MODEL_NAME` | Model name, for example `gpt-oss:120b` or `claude-sonnet-4-6` |
| `ANTHROPIC_API_KEY` | API key for `claude-*` models |
| `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` | OpenAI-compatible endpoint for every other model |
| `VIGIL_WEBHOOK_SECRET` | Bearer token required on `/webhook` |
| `KUBECONFIG` | Cluster for `kubectl-mcp` and `flux-mcp` |
| `SSH_HOSTS`, `SSH_USER`, `SSH_KEY_PATH` | NixOS hosts for `nixos-mcp`; `SSH_HOSTS` is required |
| `REPO_URL`, `GITHUB_TOKEN` | Repository that `git-mcp` commits to; both are required |
| `KUBECTL_MCP_CMD`, `FLUX_MCP_CMD`, `NIXOS_MCP_CMD`, `GIT_MCP_CMD` | Optional override of each MCP server command |

With the variables exported, start the orchestrator and check its health endpoint:

```bash
uv run --package vigil-orchestrator uvicorn orchestrator.main:app --port 9099
curl -s http://localhost:9099/healthz
```

Real runs need a reachable cluster and NixOS hosts. The eval cluster under [`infra/terraform/`](infra/terraform/README.md) provides both. The local lab under [`infra/lab/`](infra/lab/README.md) provides both on one machine.

## Branch naming

vigil follows [Conventional Branch](https://conventional-branch.github.io/).

Format: `<type>/<description>`

| Type | Alias | Use case | Example |
|------|-------|----------|---------|
| `feat/` | `feature/` | New features | `feat/watchdog-prometheus-poller` |
| `fix/` | `bugfix/` | Bug fixes | `fix/flux-mcp-reconcile-timeout` |
| `hotfix/` | - | Urgent fixes | `hotfix/rollback-gate-deadline` |
| `release/` | - | Release preparation | `release/v1.1.0` |
| `chore/` | - | Non-code tasks (deps, docs) | `chore/bump-pydantic-ai` |

Branch names use lowercase letters, numbers, and hyphens only, with no uppercase, underscores, spaces, or consecutive hyphens.

## Commit conventions

vigil follows [Conventional Commits](https://www.conventionalcommits.org/).

Format: `<type>[optional scope]: <description>`

- Types: `feat` `fix` `chore` `ci` `docs` `refactor` `perf` `test` `build`
- Scope: optional, lowercase, the component name (`kubectl-mcp`, `diagnosis`, `eval`)
- Description: lowercase and imperative, with no trailing period; 7 to 12 words is the guideline
- Subject line only, no body

The `commit-format` CI job checks the pull request title and every commit subject against this format.

```text
feat(diagnosis): add confidence threshold for os-layer escalation
fix(nixos-mcp): handle connection timeout during nixos rebuild
chore(eval): bump ollama cloud model version to latest release
```

## Pull requests

1. Run `make ci` locally.
2. Open the pull request against `main` and fill in the template.
3. The `ci-gate` check must pass before merging.
4. Pull requests are merged by squash or rebase.

## Releases

Maintainers cut releases. `make release VERSION=X.Y.Z` runs [`scripts/release.sh`](scripts/release.sh), which sets the version in every Python package and MCP server, regenerates `CHANGELOG.md` and creates the commit `chore(release): prepare vX.Y.Z`. Run it on `main` when no other work is in flight, otherwise on a `release/vX.Y.Z` branch merged through a pull request. Once `ci-gate` is green on that commit on `main`, a maintainer tags it:

```bash
git tag -a vX.Y.Z -m vX.Y.Z
git push origin vX.Y.Z
```

The release workflow publishes the GitHub release only after a green `ci-gate` on the tagged commit. Only maintainers create tags.

## Versioning

vigil uses [Semantic Versioning](https://semver.org/) with one version shared by every package and MCP server.

- MAJOR: removed environment variables or configuration, incompatible MCP tool schemas, changed gating semantics, breaking RunRecord or CLI changes, and Terraform or NixOS interface changes.
- MINOR: new capabilities and new optional inputs.
- PATCH: fixes, documentation and dependency updates.

## Code conventions

- Comments only where the intent is not obvious from the code, one line at most.
- Named constants instead of bare literals.
- Inputs validated at the earliest possible point.

Significant design choices are documented as ADRs in [`docs/adr/`](docs/adr/). Add or update an ADR when a pull request introduces or changes an architectural decision.

## AI-assisted contributions

The pull request author is accountable for every change, whatever tools produced it. Substantial AI assistance is mentioned in the pull request description.

## Security

Report vulnerabilities privately as described in [SECURITY.md](SECURITY.md), not through public issues.
