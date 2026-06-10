# Contributing to vigil

## Prerequisites

- Python >= 3.12 with [uv](https://docs.astral.sh/uv/)
- Go >= 1.26
- Terraform
- Nix / NixOS for the OS layer
- `kubectl` configured against the cluster or eval environment
- Linters `ruff` and `golangci-lint`

## Setup

```bash
uv sync
go work sync
go build ./...
```

## Testing

Run the full test suite before opening a PR:

```bash
# Python tests
uv run pytest

# Python lint
uv run ruff check .
uv run ruff format --check .

# Go
go test ./...
golangci-lint run ./...

# Terraform
terraform -chdir=infra/terraform fmt -check
terraform -chdir=infra/terraform validate
```

## Branch naming

vigil follows [Conventional Branch](https://conventional-branch.github.io/).

Format: `<type>/<description>`

| Type | Alias | Use case | Example |
|------|-------|----------|---------|
| `feat/` | `feature/` | New features | `feat/watchdog-prometheus-poller` |
| `fix/` | `bugfix/` | Bug fixes | `fix/flux-mcp-reconcile-timeout` |
| `hotfix/` | - | Urgent fixes | `hotfix/rollback-gate-deadline` |
| `release/` | - | Release preparation | `release/v0.2.0` |
| `chore/` | - | Non-code tasks (deps, docs) | `chore/bump-pydantic-ai` |

Branch names use lowercase letters, numbers, and hyphens only, with no uppercase, underscores, spaces, or consecutive hyphens.

## Commit conventions

vigil follows [Conventional Commits](https://www.conventionalcommits.org/).

Format: `<type>[optional scope]: <description>`

- Description: brief, imperative, lowercase, 7-12 words
- Scope: the component name (`kubectl-mcp`, `diagnosis`, `eval`)
- No trailing period on the subject line
- Subject line only, no body

Allowed types: `feat` `fix` `chore` `ci` `docs` `refactor` `perf` `test` `build`

Examples:

```
feat(diagnosis): add confidence threshold for os-layer escalation
fix(nixos-mcp): handle connection timeout during nixos rebuild
chore(eval): bump ollama cloud model version to latest release
```

## Code quality

- **DRY**: extract shared logic; a single change happens in one place
- **KISS**: the simplest solution that correctly solves the problem
- **SRP**: each function and module has one reason to change
- **Meaningful names**: names reveal intent without needing a comment
- **No magic numbers**: replace bare literals with named constants
- **Fail fast**: validate inputs at the earliest possible point
- **Comments**: add only where the intent is not obvious from the code itself, one line max

## Architectural decisions

Significant design choices are documented as ADRs in [`docs/adr/`](docs/adr/). Add or update an ADR when a PR introduces or changes an architectural decision.

## Pull requests

1. Ensure all tests and linters pass locally
2. Open the PR against `main`
3. Fill in the PR template
4. The `ci-gate` check must pass before merging
