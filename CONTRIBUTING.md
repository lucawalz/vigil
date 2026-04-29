# Contributing to Vigil

## Prerequisites

- Python ≥ 3.12 with [uv](https://docs.astral.sh/uv/)
- Go ≥ 1.23
- A K3s cluster or the Hetzner eval environment (see `docs/eval/runbook.md`)

## Setup

Install Python dependencies:

```bash
uv sync --all-packages
```

Build all Go MCP server binaries:

```bash
go work sync
go build ./...
```

## Testing

Run the full test suite before opening a PR:

```bash
# Python agents
uv run pytest agents/ -x

# Go MCP servers
go test ./...

# Linting
uvx ruff check .
golangci-lint run ./...
```

## Branch naming

Vigil follows [Conventional Branch](https://conventional-branch.github.io/).

Format: `<type>/<description>`

| Type | Alias | Use case | Example |
|------|-------|----------|---------|
| `feat/` | `feature/` | New features | `feat/watchdog-prometheus-poller` |
| `fix/` | `bugfix/` | Bug fixes | `fix/ssh-mcp-connection-timeout` |
| `hotfix/` | — | Urgent fixes | `hotfix/security-patch` |
| `release/` | — | Release preparation | `release/v1.2.0` |
| `chore/` | — | Non-code tasks (deps, docs) | `chore/bump-pydantic-ai` |

Rules: lowercase letters, numbers, and hyphens only — no uppercase, underscores, spaces, or consecutive hyphens.

## Commit conventions

Vigil follows [Conventional Commits](https://www.conventionalcommits.org/).

**Format**: `<type>[optional scope]: <description>`

- Description: brief, imperative, lowercase
- Scope: component name (`kubectl-mcp`, `diagnosis`, `eval`, …)
- No period at end of subject line

**Allowed types**: `feat` `fix` `chore` `ci` `docs` `refactor` `perf` `test` `build`

**Examples**:

```
feat(diagnosis): add confidence threshold for os-layer escalation
fix(ssh-mcp): handle connection timeout during nixos rebuild
chore(eval): bump ollama cloud model version to llama3.3
```

## Code quality

All contributions follow these principles:

- **DRY** — extract shared logic; a change happens in one place
- **KISS** — simplest solution that correctly solves the problem
- **SRP** — each function and module has one reason to change
- **Meaningful names** — names reveal intent without needing comments
- **No magic numbers** — use named constants
- **Fail fast** — validate inputs at the earliest possible point
- **Comments** — add only where intent isn't obvious from the code itself

## Architectural decisions

Significant design choices are documented as ADRs in [`docs/adr/`](docs/adr/). Add or update an ADR when a PR introduces or changes an architectural decision.

## Pull requests

1. Ensure all tests and linting pass locally
2. Open a PR against `main`
3. Fill in the PR template completely
4. CI must pass (ruff, golangci-lint, govulncheck, pytest, go test)

CI must pass before merging.
