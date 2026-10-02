# Changelog

All notable changes to this project are documented here.

## [1.1.0](https://github.com/lucawalz/vigil/compare/v1.0.0...v1.1.0) - 2026-10-02

### Documentation

- **eval**: Document scenarios, campaign commands and outputs ([731ed16](https://github.com/lucawalz/vigil/commit/731ed16f3211045e2f1aeb513ca49b0d40c3a5c5))
- **infra**: Describe terraform variables, state handling and provisioning ([ef86579](https://github.com/lucawalz/vigil/commit/ef86579a2e6c8f01069cc9fc2e921f31eed84717))
- **contributing**: Document make targets, commit format and the release flow ([3dc1c71](https://github.com/lucawalz/vigil/commit/3dc1c71b0297b8aefc1310c3df69565dba239e62))
- **readme**: Point setup at make targets and tighten the overview ([d555f9e](https://github.com/lucawalz/vigil/commit/d555f9ef27766381207f646638b9f1d4fbd05da7))
- **github**: Rely on the built-in security entry in the issue chooser ([0b532a9](https://github.com/lucawalz/vigil/commit/0b532a92409f8b7c4fc241ddefaec79e473b5c22))
- **github**: Point the pull request template at the make ci check ([6757072](https://github.com/lucawalz/vigil/commit/6757072658422a8fc03916e4bd9c685b1af84df9))
- **github**: Add issue forms for bug reports and feature requests ([10cd28f](https://github.com/lucawalz/vigil/commit/10cd28f2baf13d6ef993cb4720af8a8fe1a98d73))
- **security**: Describe supported versions including the archived evaluation release ([9f4e52d](https://github.com/lucawalz/vigil/commit/9f4e52d5d8bfeeb1e6a36d47db1bcdd609c7d2e5))
- Add the contributor covenant code of conduct with a contact address ([0821e53](https://github.com/lucawalz/vigil/commit/0821e53fc0c50167cd8ab67b9c50b25c2b21c936))

### Build

- **release**: Add a script that prepares a versioned release commit ([5b8cd74](https://github.com/lucawalz/vigil/commit/5b8cd74a45e5f1a8453ae51d7158f67d44a155bd))
- **infra**: Expose mcp server packages and check vendor hashes in ci ([98d4c24](https://github.com/lucawalz/vigil/commit/98d4c2471a6d1cbf187024031881100b637ae61e))
- **dev**: Add basedpyright type checking with a committed baseline ([847aa99](https://github.com/lucawalz/vigil/commit/847aa99fe3ae77bf39e4ab737c1a1286d9c5e859))
- **deps**: Update python dependencies to versions with security fixes ([9f6df44](https://github.com/lucawalz/vigil/commit/9f6df4416f24a4917331bca9fac87101baec6b25))
- **dev**: Add makefile with targets mirroring the ci workflow ([91ce7ac](https://github.com/lucawalz/vigil/commit/91ce7ac14ab1fc91e97571b50c51b4453435cfef))
- **dev**: Add nix devshell with go 1.26 and ci tooling ([dc53180](https://github.com/lucawalz/vigil/commit/dc5318069547e9687b05ca0fc21a549421b8501b))
- **deps**: Update x/crypto, go-git and x/text across all mcp servers ([740b326](https://github.com/lucawalz/vigil/commit/740b326af6c1ec500693f7e829dc67204aea9f1d))

### CI

- **release**: Publish releases only after a green ci gate on the tagged commit ([88252d8](https://github.com/lucawalz/vigil/commit/88252d8b673562aa58e29ffd46b70e5a02ba2733))
- Check commit subject format on pull requests into main ([c348302](https://github.com/lucawalz/vigil/commit/c34830247af63f50fa9e307c1a04332085c24e9d))
- **eval**: Stop campaigns early when required secrets are missing ([049e147](https://github.com/lucawalz/vigil/commit/049e147defab9e4b05a45e19b812afe13828fedd))
- Read eval environment secrets without creating deployment records ([1cc3771](https://github.com/lucawalz/vigil/commit/1cc3771fb04de877ed50d5aa6de07f4109f55c25))
- Verify downloaded gate tools and pin flux crd schemas ([1a10e20](https://github.com/lucawalz/vigil/commit/1a10e20051da92810278e45995c1d564e7125918))
- Add workflow lint job with zizmor and actionlint ([6322f88](https://github.com/lucawalz/vigil/commit/6322f886cd9f9e4af04584de9dc9bd758cb0410c))
- Run makefile targets in ci jobs and cover eval tests ([a59c566](https://github.com/lucawalz/vigil/commit/a59c566062ebd15e058c0e27f3f9f2f012950af6))
- Skip snapshot builds when the cloud token is absent ([1a5dc51](https://github.com/lucawalz/vigil/commit/1a5dc513181889ca16a5f9165027ec6d5e142857))
- Add timeouts and concurrency groups to all workflows ([f296dfc](https://github.com/lucawalz/vigil/commit/f296dfc3f9c240c8e458b7807928aa1d91304b65))
- Quote shell expansions in workflow run steps ([7fa26a5](https://github.com/lucawalz/vigil/commit/7fa26a5f51a0dd8f59ca80f4119d8d518daef55f))
- Pass secrets and untrusted values to steps through env ([9578310](https://github.com/lucawalz/vigil/commit/957831029c0ecf82c3a0a7ed82d3d89c529e4ab5))
- Grant workflow tokens least privilege and drop persisted credentials ([7312b71](https://github.com/lucawalz/vigil/commit/7312b71903447220a2e6c865177775b95647c190))

### Dependencies

- **dependabot**: Enable weekly github actions updates with a cooldown ([d0baf50](https://github.com/lucawalz/vigil/commit/d0baf50cd3b41bba479611eeb798b0c8ea484582))
- **dependabot**: Run auto-merge only for dependabot pull requests ([78c07df](https://github.com/lucawalz/vigil/commit/78c07df6d366c6e5b753371511de60385d911935))

### Miscellaneous

- **infra**: Print the group-specific kubeconfig path after apply ([29c950f](https://github.com/lucawalz/vigil/commit/29c950feab73d5d54654913c7f9dcfbdc77af7cf))
- **release**: Skip release preparation commits in the changelog ([c310d0f](https://github.com/lucawalz/vigil/commit/c310d0f1e962697324263e1afb8ea9f949fb03e9))
- **github**: Add code owners for the whole repository ([acd6531](https://github.com/lucawalz/vigil/commit/acd65316c343f10326e28f2e3bb25937d9ab436b))

## [1.0.0](https://github.com/lucawalz/vigil/releases/tag/v1.0.0)

Research prototype evaluated in the bachelor's thesis, kept unchanged at tag `v1.0.0`; the GitHub release lists every change.
