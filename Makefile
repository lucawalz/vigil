GO_MODULES := $(shell awk '/^[[:space:]]+\.\//{print $$1}' go.work)
GOVULNCHECK_VERSION := v1.8.0
TF_DIR := infra/terraform
TEST_ENV := LLM_MODEL_NAME=test-model OLLAMA_BASE_URL=http://localhost:1/v1 OLLAMA_API_KEY=sk-test VIGIL_WEBHOOK_SECRET=test-secret

.DEFAULT_GOAL := ci
.PHONY: setup fmt lint lint-py lint-go lock-check typecheck test test-py test-go build vuln tf-check nix-check ci

setup:
	uv sync --all-extras --dev --all-packages

fmt:
	uv run ruff format .
	uv run ruff check --fix .
	gofmt -w mcp-servers
	terraform -chdir=$(TF_DIR) fmt -recursive

lint: lint-py lint-go
	terraform -chdir=$(TF_DIR) fmt -check -recursive

lint-py:
	uv run ruff check .
	uv run ruff format --check .

lint-go:
	@set -e; for m in $(GO_MODULES); do echo "golangci-lint $$m"; (cd $$m && golangci-lint run ./...); done

lock-check:
	uv lock --check

typecheck:
	uv run basedpyright

test: test-py test-go

test-py:
	env $(TEST_ENV) uv run pytest tests/ -x --tb=short -q $(ARGS)

test-go:
	@set -e; for m in $(GO_MODULES); do echo "go test $$m"; (cd $$m && CGO_ENABLED=0 go test ./... -count=1); done

build:
	@set -e; for m in $(GO_MODULES); do echo "go build $$m"; (cd $$m && CGO_ENABLED=0 go build ./...); done

vuln:
	@set -e; for m in $(GO_MODULES); do echo "govulncheck $$m"; (cd $$m && GOWORK=off go run golang.org/x/vuln/cmd/govulncheck@$(GOVULNCHECK_VERSION) ./...); done

tf-check:
	terraform -chdir=$(TF_DIR) fmt -check -recursive
	terraform -chdir=$(TF_DIR) init -backend=false -input=false
	terraform -chdir=$(TF_DIR) validate

nix-check:
	cd infra/nixos && nix flake check --no-build --all-systems

ci: lint lock-check typecheck test build vuln tf-check
