#!/usr/bin/env bash
set -euo pipefail

GIT_CLIFF="git-cliff==2.14.2"
VERSION_PATTERN='^[0-9]+\.[0-9]+\.[0-9]+(-rc\.[0-9]+)?$'
PACKAGES=(vigil-common vigil-diagnosis vigil-eval vigil-lab vigil-orchestrator vigil-remediation vigil-watchdog)
GIT_MCP_SERVER=mcp-servers/git-mcp/internal/server/server.go
LITERAL_MCP_SERVERS=(
  mcp-servers/flux-mcp/internal/server/server.go
  mcp-servers/kubectl-mcp/internal/server/server.go
  mcp-servers/nixos-mcp/internal/server/server.go
)
CHANGELOG=CHANGELOG.md
THESIS_RELEASE_LINE="Research prototype evaluated in the bachelor's thesis, kept unchanged at tag \`v1.0.0\`; the GitHub release lists every change."

die() {
  echo "release: $*" >&2
  exit 1
}

replace_in_place() {
  local expression=$1 file=$2
  sed -i.bak -E "$expression" "$file"
  rm -f "$file.bak"
  if git diff --quiet -- "$file"; then
    die "version string not found in $file"
  fi
}

write_changelog() {
  if [[ -f $CHANGELOG ]]; then
    uvx "$GIT_CLIFF" --tag "$tag" --unreleased --prepend "$CHANGELOG"
    return
  fi
  uvx "$GIT_CLIFF" --tag "$tag" --unreleased --output "$CHANGELOG"
  local repo_url
  repo_url=$(sed -n -E 's|^## \[[^]]*\]\((https://[^)]*)/compare/.*|\1|p' "$CHANGELOG" | head -n 1)
  [[ -n $repo_url ]] || die "repository URL not found in the generated $CHANGELOG"
  printf '## [1.0.0](%s/releases/tag/v1.0.0)\n\n%s\n' "$repo_url" "$THESIS_RELEASE_LINE" >>"$CHANGELOG"
}

[[ $# -eq 1 ]] || die "usage: scripts/release.sh X.Y.Z[-rc.N]"
version=$1
[[ $version =~ $VERSION_PATTERN ]] || die "invalid version '$version', expected X.Y.Z or X.Y.Z-rc.N"
tag="v$version"

cd "$(git rev-parse --show-toplevel)"
[[ -z $(git status --porcelain) ]] || die "working tree is not clean"
git rev-parse -q --verify "refs/tags/$tag" >/dev/null && die "tag $tag already exists"
pep440_version=${version/-rc./rc}
[[ $(uv version --short --frozen) != "$pep440_version" ]] || die "version $version is already set"

uv version --frozen "$version"
for package in "${PACKAGES[@]}"; do
  uv version --frozen --package "$package" "$version"
done
uv lock

replace_in_place "s/^(const serverVersion = )\"[^\"]+\"/\1\"$version\"/" "$GIT_MCP_SERVER"
for file in "${LITERAL_MCP_SERVERS[@]}"; do
  replace_in_place "s/(NewMCPServer\(\"[a-z-]+\", )\"[^\"]+\"/\1\"$version\"/" "$file"
done

write_changelog

git add pyproject.toml agents/*/pyproject.toml eval/pyproject.toml uv.lock mcp-servers/*/internal/server/server.go "$CHANGELOG"
git commit -m "chore(release): prepare $tag"

cat <<EOF
Release commit for $tag created on branch $(git branch --show-current).
Next steps:
  1. Push the branch (directly to main, or as release/$tag with a pull request) and wait for a green ci-gate.
  2. Tag the commit on main: git tag -a $tag -m $tag <commit>
  3. Push the tag: git push origin $tag
EOF
