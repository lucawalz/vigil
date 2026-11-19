---
status: Accepted
date: 2026-11-19
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0018: Releases through release-please

## Context and Problem Statement

The public repositories under `lucawalz` share one release standard, kept in `lucawalz/.github`. release-please opens a release pull request from the Conventional Commit pull request titles merged since the last release, a tag ruleset lets only the release GitHub App and the admin create `v*` tags, and a shared workflow creates the GitHub release and marks the released pull requests and issues.

Vigil carries one version across the root project, the seven Python workspace packages, their entries in `uv.lock` and the four Go MCP servers. Its release series runs `v1.0.0`, `v1.1.0` and `v2.0.0`, and `CHANGELOG.md` holds the notes for each of them.

## Decision Drivers

- One release flow across the released repositories, maintained in one place
- Every version string in the repository moves in the same commit as the changelog
- Release notes come from the Conventional Commits the repository already uses
- The existing tags and `CHANGELOG.md` sections stay as they are, and the series continues from `v2.0.0`
- A release is published only through a deliberate merge

## Considered Options

- release-please through the shared release workflow
- Tag-based releases with git-cliff, as in ADR-0016
- release-please through a workflow kept in this repository

## Decision Outcome

Chosen option: "release-please through the shared release workflow", because it gives vigil the same release flow as the other released repositories, writes every version string in one release pull request, and keeps the App token, tag and release steps in one shared workflow.

`release-please-config.json` uses the `python` release type, which writes the root `pyproject.toml` and `CHANGELOG.md`. Its `extra-files` write the same version into the seven member `pyproject.toml` files, into the `vigil` and `vigil-*` package entries of `uv.lock` through a TOML path filter, and into the four MCP server version literals, each marked with an `x-release-please-version` comment. `include-component-in-tag` is off, so tags keep the `vX.Y.Z` form. `.release-please-manifest.json` starts at `2.0.0`, so the next release continues from `v2.0.0`. The changelog uses release-please's default sections for the `python` release type, and new sections are added above the existing ones.

The release pull request opens as a draft with the `held` label (`draft-pull-request`, `extra-label`) and is updated on every push to `main`. Merging it creates the tag and a draft release (`draft`, `force-tag-creation`), and the shared workflow publishes the release, then comments on and adds the `released` label to every merged pull request in it and the issues those pull requests close.

`.github/workflows/release-please.yml` calls the shared workflow at a pinned commit with the `RELEASE_APP_ID` and `RELEASE_APP_PRIVATE_KEY` secrets.

### Consequences

- Good: A release is one merge of the release pull request, and every version string, the lockfile entries and the changelog move in that commit
- Good: Tags come from the release App and point at the merged release commit
- Good: The `lockfile-drift` job runs on the release pull request, so `ci-gate` confirms that `uv.lock` matches the new versions before the merge
- Neutral: New `CHANGELOG.md` sections use release-please's heading and bullet format, above the earlier sections
- Neutral: A new workspace package or MCP server needs its own `extra-files` entry, and a new MCP server also needs the marker comment on its version literal

**Validation Status:** Pending. Confirmed once the release pull request opens as a draft with the `held` label and its `ci-gate` passes.

### Confirmation

The decision holds as long as:

- `release-please-config.json` and `.release-please-manifest.json` exist at the repository root, and the manifest version equals the root `pyproject.toml` version
- `.github/workflows/release-please.yml` calls the shared release workflow pinned to a commit SHA
- Every member `pyproject.toml`, every `vigil` and `vigil-*` entry in `uv.lock` and every MCP server version literal carries the manifest version
- No other workflow in the repository creates tags or releases

### Pros and Cons of the Options

#### release-please through the shared release workflow

- Good: The release flow, its pinned actions and its App token handling are maintained once for every released repository
- Good: Version bumps follow from Conventional Commit types, so the version number and the changelog come from the same commits
- Good: `extra-files` covers TOML paths and marker comments, so the Python packages, the lockfile and the Go servers share one version
- Bad: The changelog format and sections are release-please's, configured through its options rather than a template

#### Tag-based releases with git-cliff, as in ADR-0016

- Good: git-cliff renders the changelog from a template in `cliff.toml`
- Bad: The shared `release-tags-creation` ruleset reserves `v*` tag creation for the release App and the admin, so a release cut by pushing a tag would follow a different path from every other released repository under the same ruleset

#### release-please through a workflow kept in this repository

- Good: Every step is visible in this repository
- Bad: The App token, draft release, publish and release comment steps would exist twice, here and in `lucawalz/.github`, so a fix to the shared release flow would have to be repeated in vigil by hand

## More Information

- Release tagging and changelog automation for `v1.0.0` to `v2.0.0`: `docs/adr/0016-release-tagging-and-changelog-automation.md`
- Shared release workflow: [`lucawalz/.github`](https://github.com/lucawalz/.github/blob/main/.github/workflows/release.yml)
- Release steps for maintainers: the Releases section of `CONTRIBUTING.md`
