---
status: Accepted
date: 2026-06-17
decision-makers: [Luca Walz]
consulted: []
informed: []
---

# ADR-0016: Release tagging and changelog automation

## Context and Problem Statement

The thesis must cite the exact version of Vigil that was evaluated, and an examiner must be able to check out that version and reproduce the evaluation campaigns. A moving `main` defeats this: Dependabot opened patch and minor version-update PRs that `dependabot-auto-merge.yml` merged automatically, advancing `main` mid-campaign. Each merge changed dependency versions underneath in-flight evaluation runs, repeatedly disrupting campaigns and leaving "the evaluated commit" ambiguous — a run started against one tree finished against another.

The project needs a stable, citable reference that pins the evaluated tree, plus human-readable release notes that explain what each version contains without hand-authoring a changelog.

## Decision Drivers

- The thesis requires a single, permanent, checkoutable reference for the evaluated version; a SHA on a moving branch is neither memorable nor stable against force-pushes or rebases
- Dependabot auto-merges advanced `main` during campaigns, so the dependency tree the agent ran against was non-deterministic across a single campaign
- Release notes must be reproducible from commit history rather than hand-written, since the repository already enforces Conventional Commits
- The monorepo spans Python agents, Go MCP servers, NixOS modules, and Terraform; any changelog tool must be language-agnostic and not assume a single package manifest

## Considered Options

- Tag-based SemVer releases with git-cliff generating notes from Conventional Commits, triggered by a `release.yml` workflow on `v*.*.*` tag pushes
- GitHub-native automatically generated release notes
- release-please for automated version-bump PRs and changelog management

## Decision Outcome

Chosen option: "tag-based SemVer releases with git-cliff", because it produces a permanent, examiner-checkoutable reference for the evaluated version, derives human-readable notes directly from the Conventional Commits the repository already enforces, and adds no version-management machinery to a polyglot monorepo with no single package manifest.

Releases are SemVer tags of the form `v*.*.*`. Pushing such a tag triggers a `release.yml` workflow that runs git-cliff against the commit history, using the `cliff.toml` configuration to group Conventional Commits into a categorised changelog, and publishes the result as the GitHub Release notes. The workspace version is bumped to 1.0.0, and **`v1.0.0` is the frozen version evaluated in the thesis** — every model evaluation campaign runs against that tag.

To keep the evaluated tree stable, Dependabot version updates are paused for the duration of the evaluation freeze: the `updates` entries in `.github/dependabot.yml` are commented out so Dependabot opens no PRs, and they are restored once the evaluation concludes.

### Consequences

- Good: `git checkout v1.0.0` yields a permanent, immutable reference to the exact evaluated tree; the thesis cites one unambiguous tag
- Good: Release notes are generated automatically from Conventional Commits, so the changelog is reproducible from history and needs no manual authoring
- Good: The evaluated dependency tree is frozen for the duration of the campaign, so a single campaign runs against one consistent tree from start to finish
- Bad: Dependabot is paused, so dependencies receive no patch, minor, or security updates until the `updates` entries are restored after the evaluation
- Neutral: Releases are cut manually by pushing a tag; there is no automated version-bump PR, so the decision to release and the version number are explicit human actions
- Neutral: After the evaluation harness was corrected for scenario-ground-truth leakage, `v1.0.0` is re-pointed to the corrected commit rather than minting a new version, so the thesis keeps one cited tag; clones that fetched the earlier tag must re-fetch the moved `v1.0.0`, and the campaigns recorded against the earlier commit are superseded (see ADR-0008)

**Validation Status:** Pending. Confirmed once `v1.0.0` is re-pointed to the corrected commit, `release.yml` publishes git-cliff-generated notes for it, and the thesis cites the tag.

### Confirmation

The decision holds as long as:

- `cliff.toml` exists at the repository root and configures git-cliff to group Conventional Commits into the changelog
- `.github/workflows/release.yml` exists and triggers on `v*.*.*` tag pushes, generating release notes with git-cliff
- The `updates` entries in `.github/dependabot.yml` remain commented out for the duration of the evaluation freeze, and are restored afterward
- The thesis cites tag `v1.0.0` as the evaluated version, and every model campaign runs against that tag

### Pros and Cons of the Options

#### Tag-based SemVer releases with git-cliff

- Good: A SemVer tag is a permanent, checkoutable reference; `v1.0.0` pins the evaluated tree for the examiner regardless of later commits
- Good: git-cliff is purpose-built for Conventional Commits, which the repository already enforces, so the changelog falls out of existing commit discipline
- Good: Language-agnostic — it reads git history, not package manifests, which suits a monorepo spanning Python, Go, NixOS, and Terraform
- Good: Minimal configuration in a single `cliff.toml`; no version-management machinery or bot PRs to maintain
- Bad: Releases are cut manually by pushing a tag, so a forgotten tag means no release; the cadence depends on a deliberate human step

#### GitHub-native automatically generated release notes

- Bad: GitHub's auto-notes group entries by PR label and author rather than Conventional Commit type, so the categorised changelog the repository's commit discipline already encodes is discarded in favour of a flat PR list that does not match the thesis's commit taxonomy

#### release-please

- Bad: release-please maintains version state through bot-authored release PRs and per-language manifest plugins; in this polyglot monorepo with no single package version it would either require configuring a manifest per ecosystem or fight the absence of one, adding version-management machinery the project does not otherwise need

## More Information

- GitHub Actions eval campaign runner that consumes the frozen tag: `docs/adr/0010-github-actions-eval-runner.md`
- Evaluation model selection across the campaigns run against `v1.0.0`: `docs/adr/0008-evaluation-model-selection.md`
