GO_MODULES := $(shell awk '/^[[:space:]]+\.\//{print $$1}' go.work)
GOVULNCHECK_VERSION := v1.8.0
ACTIONLINT_VERSION := v1.7.12
TF_DIR := infra/terraform
NIX_DIR := infra/nixos
MCP_SERVERS_NIX := $(NIX_DIR)/pkgs/mcp-servers.nix
TEST_ENV := LLM_MODEL_NAME=test-model OLLAMA_BASE_URL=http://localhost:1/v1 OLLAMA_API_KEY=sk-test VIGIL_WEBHOOK_SECRET=test-secret
VENDOR_HASH_EXPR := { name }: let flake = builtins.getFlake "git+file://$(CURDIR)?dir=$(NIX_DIR)"; pkgs = flake.inputs.nixpkgs.legacyPackages.$${builtins.currentSystem}; in (import ./$(MCP_SERVERS_NIX) { inherit pkgs; self = flake; }).$${name}.goModules.overrideAttrs { outputHash = pkgs.lib.fakeHash; }

.DEFAULT_GOAL := ci
.PHONY: setup fmt lint lint-py lint-go lock-check typecheck test test-py test-go build vuln tf-check nix-check workflow-lint vendor-hash release ci

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
	cd $(NIX_DIR) && nix flake check --no-build --all-systems

workflow-lint:
	@command -v shellcheck >/dev/null || { echo "shellcheck is required by actionlint" >&2; exit 1; }
	uv run zizmor --offline .github/workflows
	GOWORK=off go run github.com/rhysd/actionlint/cmd/actionlint@$(ACTIONLINT_VERSION)

vendor-hash:
	@set -e; for m in $(GO_MODULES); do \
		n=$$(basename $$m); \
		h=$$(nix build --impure --no-link --expr '$(VENDOR_HASH_EXPR)' --argstr name $$n 2>&1 | awk '/got:/ {print $$2}'); \
		test -n "$$h" || { echo "vendor hash for $$n not computed" >&2; exit 1; }; \
		sed -i.bak "s|name = \"$$n\"; vendorHash = \"[^\"]*\"|name = \"$$n\"; vendorHash = \"$$h\"|" $(MCP_SERVERS_NIX); \
		rm -f $(MCP_SERVERS_NIX).bak; \
		grep -q "name = \"$$n\"; vendorHash = \"$$h\"" $(MCP_SERVERS_NIX) || { echo "vendor hash for $$n not written" >&2; exit 1; }; \
		echo "$$n $$h"; \
	done

release:
	scripts/release.sh $(VERSION)

ci: lint lock-check typecheck test build vuln tf-check workflow-lint
