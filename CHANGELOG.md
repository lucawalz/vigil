# Changelog

All notable changes to this project are documented here.

## [2.0.1](https://github.com/lucawalz/vigil/compare/v2.0.0...v2.0.1) (2026-11-19)


### Bug Fixes

* **ci:** pin actions by sha and require hash pins in zizmor ([0327856](https://github.com/lucawalz/vigil/commit/0327856532aa3125b4cb91ef4c7827cc2e1ac658))


### Documentation

* **readme:** add results section linking eval campaign reports ([025755b](https://github.com/lucawalz/vigil/commit/025755b8e978bfe155d225298e27fd7a9fc34123))
* **readme:** clarify results scoring and name the thesis only model ([08fe0e1](https://github.com/lucawalz/vigil/commit/08fe0e1351f4830566d724adf944be77dd67dc85))

## [2.0.0](https://github.com/lucawalz/vigil/compare/v1.1.0...v2.0.0) - 2026-11-07

### Breaking changes

- **infra**: Terraform takes `github_repository`, `campaign_run_id` and `operator_cidrs`, and authenticates through two GitHub Apps with `github_app_client_id`, `github_app_private_key`, `harness_app_client_id` and `harness_app_private_key`
- **eval**: The campaign reads `VIGIL_APP_CLIENT_ID`, `VIGIL_APP_PRIVATE_KEY`, `VIGIL_HARNESS_APP_CLIENT_ID` and `VIGIL_HARNESS_APP_PRIVATE_KEY` from the `eval` environment and requires a branch ruleset with the `remediation-gate` check on `eval/**/*`
- **nixos**: Host configurations are named `vigil-control-plane-1`, `vigil-worker-1`, `vigil-worker-2` and `vigil-agent`, with `-lab-<arch>` variants for the local lab
- **git-mcp**: The orchestrator owns the gate wait, merge, close and reconcile after `create_pr`; `clone_repo` opens a fresh session per run and `read_file` reads from that session

### Features

- **infra**: Name each snapshot after its run as well as its nixos hash ([85a8f44](https://github.com/lucawalz/vigil/commit/85a8f4440022c300c472501df420049f2f7e7239))
- **nixos**: Wait for each partition link before disko formats it ([58f73f1](https://github.com/lucawalz/vigil/commit/58f73f1cc7a48e5439a04782ea91508dbb89a360), [#1473](https://github.com/lucawalz/vigil/issues/1473))
- **orchestrator**: Commit a staged generation once its verdict confirms it ([83d12d7](https://github.com/lucawalz/vigil/commit/83d12d7cc2ceecd0523641a96f92e27b2d3e0807))
- **orchestrator**: Serialise stage calls and commits on one run lock ([5e18d39](https://github.com/lucawalz/vigil/commit/5e18d3906836efd539d34fd169fa3567d5b46eeb))
- **watchdog**: Count a node as healthy only after its lease renews ([96bb238](https://github.com/lucawalz/vigil/commit/96bb23854701d89514518a7c1378875922f0b6db))
- **infra**: Let the eval runner read node leases in kube-node-lease ([067277e](https://github.com/lucawalz/vigil/commit/067277eee806e92401cfd604262b5765d312c5d4))
- **kubectl-mcp**: Report the node lease renew time in describe_node ([b6c9a70](https://github.com/lucawalz/vigil/commit/b6c9a70c6110a51462fa73cdb4daf2e0cad50a23))
- **eval**: End pending stages before os resets disarm the rollback timer ([d01117a](https://github.com/lucawalz/vigil/commit/d01117a2a8293831b396ec25ecf49c194d4577b2))
- **orchestrator**: Bound nixos-mcp calls by the rebuild lock wait and dial budget ([efba8e9](https://github.com/lucawalz/vigil/commit/efba8e987bfce3b16131e8ac4ec60789ea78770d))
- **nixos**: Skip auto-reconciler rounds while the rollback timer is armed ([b3a3a7b](https://github.com/lucawalz/vigil/commit/b3a3a7b4979e9fc3669f68624dadc6f37d55adff))
- **nixos-mcp**: Arm the rollback timer under the shared nixos rebuild lock ([9662380](https://github.com/lucawalz/vigil/commit/9662380353a338ce582ca8cfa898f72b38719020))
- **eval**: Disarm the rollback timer before each os reset restores its baseline ([a8d7a7d](https://github.com/lucawalz/vigil/commit/a8d7a7dc05e504ec4d0270f260c29ef6a4b2318d))
- **orchestrator**: Commit the probed host only after a verdict covering its stages ([48ff611](https://github.com/lucawalz/vigil/commit/48ff611d105218a810bb446eabf186596607eb15))
- **watchdog**: Restart the healthy streak whenever a stage call returns ([0e7870b](https://github.com/lucawalz/vigil/commit/0e7870b95af635dd5bfc157dacf745c593300c73))
- **remediation**: Record the host of every stage call that returns ([ea53f6d](https://github.com/lucawalz/vigil/commit/ea53f6d2b58b32782a116bfa5fb6c3ae7ef84fa8))
- **watchdog**: Treat an os target without a resolvable check as indeterminate ([50db294](https://github.com/lucawalz/vigil/commit/50db294123a63fd89a06d23b915d02c3cad43b0f))
- **nixos-mcp**: Commit the running system only while the rollback timer is armed ([1e40e84](https://github.com/lucawalz/vigil/commit/1e40e84abd8f592f4dec9ce159d00c677548a316))
- **remediation**: Fence diagnosis free text and external tool output ([388f28b](https://github.com/lucawalz/vigil/commit/388f28b0bcc697747c2978041b00abc9fcb1c4d8))
- **diagnosis**: Fence fetched context and read tool output per run ([81458ee](https://github.com/lucawalz/vigil/commit/81458ee14fec06737613cd79d476124f2e47a314))
- **common**: Add per-run nonce fence and a fencing toolset ([7883644](https://github.com/lucawalz/vigil/commit/78836447ca4c90d9a1140634584d578cb62ec9bc))
- **git-mcp**: Remove the session clone when the server exits ([83aca4a](https://github.com/lucawalz/vigil/commit/83aca4a820044a73449821181f9dc2aef8ba2af6))
- **eval**: Wait for and score the final try of each incident ([ca7c5c6](https://github.com/lucawalz/vigil/commit/ca7c5c6e6424ad596673f3a7177b35aed3b92c95))
- **orchestrator**: Report the run timeout on the health endpoint ([84c1d49](https://github.com/lucawalz/vigil/commit/84c1d49e09e1416e22ee173a7e84e9ed08cad7a9))
- **lab**: Stop the agent through its shutdown drain before killing the group ([5e0a3fd](https://github.com/lucawalz/vigil/commit/5e0a3fd469ad2e525c4da7f1dbf89e7847623df4))
- **infra**: Run uvicorn directly and give the unit time to drain ([c19f33b](https://github.com/lucawalz/vigil/commit/c19f33b2e122d5786239b2ff39dbc76ae64f01f2))
- **orchestrator**: Drain active runs and queued tries before closing mcp sessions ([72907e4](https://github.com/lucawalz/vigil/commit/72907e4e05749eff57562eb66866b823ec3ea2e9))
- **orchestrator**: Check the failed-gate path and rollback budget at startup ([199e5c2](https://github.com/lucawalz/vigil/commit/199e5c2ab48d383ca0742bf791c5031a04b0f838))
- **orchestrator**: Queue up to three verified tries per incident with factual hints ([db38814](https://github.com/lucawalz/vigil/commit/db388143688df5860a7ba35f10764a2fd37f3635))
- **diagnosis**: List the facts of earlier tries before the fault summary ([250e34d](https://github.com/lucawalz/vigil/commit/250e34d48b7bc8891429a484588be4af796f1eec))
- **orchestrator**: Verify a rollback at the revert revision before reporting success ([124145f](https://github.com/lucawalz/vigil/commit/124145f932053da75b2a32b7726cf9cd3e21b614))
- **remediation**: Keep the reconciler revision read for the orchestrator ([fbb8ea7](https://github.com/lucawalz/vigil/commit/fbb8ea74d7090fbcc4dcca641ce3b22cf5917f8a))
- **nixos-mcp**: Read the revision the auto-reconciler last applied ([2a06a8d](https://github.com/lucawalz/vigil/commit/2a06a8db5ea7e7053c1e155d3219d3b22197aa02))
- **orchestrator**: Roll back live merges in one finaliser outside the run deadline ([b848958](https://github.com/lucawalz/vigil/commit/b848958257cfec2306d151fe5f33252a45a4eb20))
- **orchestrator**: Run one diagnosis and remediation try per run ([91a6b41](https://github.com/lucawalz/vigil/commit/91a6b41bd602c3919915564fe54df3b7b7321f89))
- **git-mcp**: Read files only from the session opened by clone_repo ([2873a4b](https://github.com/lucawalz/vigil/commit/2873a4bc603acd2bf910853f7deebe55a15c0427))
- **git-mcp**: Start a fresh session on every clone_repo call ([c2c28c7](https://github.com/lucawalz/vigil/commit/c2c28c765d2b09ca10b78b91f74954baeac562a1))
- **orchestrator**: Fit one attempt into the run deadline at startup ([98833ce](https://github.com/lucawalz/vigil/commit/98833ce51f8ae237c6179787544e4a5f6a80bda5))
- **remediation**: End git paths at create_pr with orchestrator-owned tools hidden ([0c5b10c](https://github.com/lucawalz/vigil/commit/0c5b10c0ab2993a8d51a615e76d0a52a9fa4cc2c))
- **orchestrator**: Own the gate, merge and reconcile after create_pr ([0d07bba](https://github.com/lucawalz/vigil/commit/0d07bba7d14f1889858050035580274f41204d5f))
- **diagnosis**: Read declared state from the orchestrator-opened git session ([6f42ff6](https://github.com/lucawalz/vigil/commit/6f42ff680403b071746ece97c675a3041d475232))
- **orchestrator**: Open one git-mcp session per run before diagnosis ([544305f](https://github.com/lucawalz/vigil/commit/544305f03b99ff538d80e3f75c5d9f3922a0862e))
- **flux-mcp**: Reconcile the git source first and refuse suspended kustomizations ([bcea34b](https://github.com/lucawalz/vigil/commit/bcea34bbbddca6e4363edab228ed9babf96e0ce3))
- **git-mcp**: Treat an already deleted branch as a successful cleanup ([39027a8](https://github.com/lucawalz/vigil/commit/39027a88e3477513419e2540a633a25d33baa0d6))
- **remediation**: Keep human-review pull requests away from gate and revert tools ([b088a33](https://github.com/lucawalz/vigil/commit/b088a33eca22a367aabb276022466ece16910264))
- **orchestrator**: Call gate tools with the server-side wait budget only ([65f921f](https://github.com/lucawalz/vigil/commit/65f921fd04260da73916b362f202562cce79c299))
- **git-mcp**: Merge gated pull requests through the api at the checked head ([f07544e](https://github.com/lucawalz/vigil/commit/f07544e60159599a6daa6ac702b21a21ff4ba29e))
- **git-mcp**: Find the gate check directly and poll through transient errors ([064b3d3](https://github.com/lucawalz/vigil/commit/064b3d39661af99e1e53bf57206e3bc474887c98))
- **git-mcp**: Follow force-updated base branches and report fetch errors precisely ([3dc004a](https://github.com/lucawalz/vigil/commit/3dc004a53460840d733492bf7c41c56b2194e628))
- **git-mcp**: Refuse shallow reverts and abort a conflicting revert cleanly ([e39b148](https://github.com/lucawalz/vigil/commit/e39b148b20333a4a14e2754fa3851f237816ff38))
- **remediation**: Clean up after every unsuccessful gate wait ([a785fb8](https://github.com/lucawalz/vigil/commit/a785fb8243150b82678b2102868e5d09736226d3))
- **orchestrator**: Derive every gate wait timeout from one ordered budget ([5377c72](https://github.com/lucawalz/vigil/commit/5377c724f933fb807b12aeff1ffcc63702a68b3a))
- **git-mcp**: Disable auto-merge and report the final state after gate waits ([0637c90](https://github.com/lucawalz/vigil/commit/0637c9061357f8d46e721ac0115e279b94db57a1))
- **infra**: Generate host and agent keys on first boot of each server ([dcb74f4](https://github.com/lucawalz/vigil/commit/dcb74f46e46ad3bedb7d23f2797dd10a7a3a3aa2))
- **infra**: Limit ssh and api access to the operator addresses ([8f36464](https://github.com/lucawalz/vigil/commit/8f36464e82149c50c2f9e14cb3f264adc7cb72ca))
- **infra**: Keep agent secrets out of interactive root shells ([6c7ccce](https://github.com/lucawalz/vigil/commit/6c7ccce69db6457ca33e1ea803e08807213eb808))
- **k3s**: Write the cluster kubeconfig readable by root only ([3a9fda5](https://github.com/lucawalz/vigil/commit/3a9fda553cacb97ed9b647aba1964aa3b4dd1c34))
- **k3s**: Encrypt secrets at rest and record an api audit log ([c96a912](https://github.com/lucawalz/vigil/commit/c96a9126d80ed92029ba4a94fd34a919beed872b))
- **lab**: Push lab harness commits as the eval harness app ([8d217a4](https://github.com/lucawalz/vigil/commit/8d217a41ee02ee0ed7b441747326179208d0b473))
- **infra**: Deliver a separate github app key for the eval harness ([5acf27c](https://github.com/lucawalz/vigil/commit/5acf27c5127d1281809bff0872432fb40025c8cc))
- **orchestrator**: Give the gated rollback revert its own call timeout ([1c647fd](https://github.com/lucawalz/vigil/commit/1c647fd8e11ef65e971d2d99d4c25249cd2ce2f9))
- **git-mcp**: Serve a separate credential for the eval harness identity ([b6fabfe](https://github.com/lucawalz/vigil/commit/b6fabfeff86bcdb5bb8803240c2f6889089f4b8a))
- **git-mcp**: Revert remediation merges through a gated pull request ([c9e1449](https://github.com/lucawalz/vigil/commit/c9e1449d35f97e8ab12492f0a508ca3ce6c550d5))
- **lab**: Authenticate lab pushes through the git-mcp credential helper ([7ff384b](https://github.com/lucawalz/vigil/commit/7ff384b3e16a0f74281b6e51848238e3449286b1))
- **infra**: Deliver the github app key to the agent host ([723adc3](https://github.com/lucawalz/vigil/commit/723adc37277114292341946636cda7c6f6f0b90a))
- **git-mcp**: Authenticate as a github app with refreshing tokens ([793da75](https://github.com/lucawalz/vigil/commit/793da756c589a40417753fc0ca474c0f07fc6708))
- **infra**: Share the agent environment defaults across lab and hetzner ([0d8a763](https://github.com/lucawalz/vigil/commit/0d8a7638f90880dcca71f7ef722cc5e4fb1eaffa))
- **infra**: Generate the webhook secret per cluster in terraform ([d2f2885](https://github.com/lucawalz/vigil/commit/d2f28852a02a4517c5acf70390a0ce51bbdb0ce6))
- **infra**: Take the github repository as one input for forks ([6eab89f](https://github.com/lucawalz/vigil/commit/6eab89fb3091ca98cf6d634942ff30d51868be12))
- **eval**: Open the symptom window once flux has taken up the inject ([e324afd](https://github.com/lucawalz/vigil/commit/e324afde0ae57575b7e5af9e2714edee2a8d6c20))
- **eval**: Offer gpt-oss:120b as the open-weight campaign model ([a5fc482](https://github.com/lucawalz/vigil/commit/a5fc4822fda47ce42beacde6200819b99fa51d16))
- **infra**: Scope hetzner resources to one run and sweep them after use ([0e8a3d8](https://github.com/lucawalz/vigil/commit/0e8a3d8a2e49a861fdc1475496416bdc6b34537a))
- **infra**: Add the lab flux cluster with local storage and alertmanager ([1827c79](https://github.com/lucawalz/vigil/commit/1827c7997a3bc473087acfe4bd96fa767f88fac1))
- **lab**: Boot the nixos hosts as local qemu vms ([05b2734](https://github.com/lucawalz/vigil/commit/05b273474c7308fec9147ab79c154508f65766b0))
- **lab**: Launch the native agent with the lab environment and ssh wrapper ([130f70e](https://github.com/lucawalz/vigil/commit/130f70eaf7218a8e27ce462cc53a7ca338f7cfc7))
- **lab**: Bootstrap the lab cluster with kubeconfigs, rbac tokens and flux ([64fad1b](https://github.com/lucawalz/vigil/commit/64fad1b9f5cc9faab970a36cdb611640f43e0a1c))
- **lab**: Install golden and in-place disks from the installer iso ([74e91bd](https://github.com/lucawalz/vigil/commit/74e91bde2a8bbe76844e0a785cc16a7659985f6a))
- **lab**: Start the macos image builder behind one exclusive start guard ([8a7209e](https://github.com/lucawalz/vigil/commit/8a7209e513937fbcbf4b732dd58943b9ae250d1f))
- **lab**: Relay hub frames and drop them for stalled clients ([feaad88](https://github.com/lucawalz/vigil/commit/feaad8860841dc5eeeff1cb68eb8de20b41172fd))
- **lab**: Add the lab runner package with address plan and qemu arguments ([c98bcca](https://github.com/lucawalz/vigil/commit/c98bcca1c67516901db583f41432c195f9c90411))
- **infra**: Run the memory load sidecar on multi-arch stress-ng pinned by digest ([f9d67a5](https://github.com/lucawalz/vigil/commit/f9d67a523acc4972e3f1764c7c600e02eabae711))
- **eval**: Record the run target and aggregate one target at a time ([18ac664](https://github.com/lucawalz/vigil/commit/18ac664070111256247ed4c846775d7f8f87b21e))
- **eval**: Run scenario scripts against a configurable eval branch on any os ([027d02c](https://github.com/lucawalz/vigil/commit/027d02c960bce25966b1e1ac5567d6e85e48942a))
- **nixos-mcp**: Rebuild hosts from their validated flake attribute file ([4b70d93](https://github.com/lucawalz/vigil/commit/4b70d9366eacee1a644842cb2decd8f5d767d8e7))
- **nixos-mcp**: Accept name and port ssh host entries as the allow-list ([6b7ec90](https://github.com/lucawalz/vigil/commit/6b7ec9019bb4435b1332c8de17dfbd77e8160033))
- **infra**: Sync flux from one script over public https for every target ([4188e9b](https://github.com/lucawalz/vigil/commit/4188e9b6471e66274c1f731feb0895b46a25ab9a))
- **infra**: Derive terraform and packer host names and addresses from inventory ([6327260](https://github.com/lucawalz/vigil/commit/632726078f3a20287a6d9ecb736f80b6d8c1cb54))
- **nixos**: Read k3s cidrs from the address plan and branch from file ([bae58bb](https://github.com/lucawalz/vigil/commit/bae58bbf3a09c147f612f73dacb040d8784f352b))
- **nixos**: Expose lab host configurations and packages for three systems ([f1414ad](https://github.com/lucawalz/vigil/commit/f1414ad54765f83b91553ecf1cbd53343c0191b6))
- **nixos**: Build every host through one builder with hetzner and lab profiles ([07190e4](https://github.com/lucawalz/vigil/commit/07190e48453f877f9108616dd5148fe626875019))
- **infra**: Add host inventory and derived address plan for all targets ([3edb283](https://github.com/lucawalz/vigil/commit/3edb283c375756702f9bbca7209885653aef2b6b))

### Bug Fixes

- **lab**: Keep the lab ssh config from overriding other hosts ([91bc347](https://github.com/lucawalz/vigil/commit/91bc347ce6f9bcf73e3b3d617df572e7060b05dd))
- **lab**: Authenticate scratch clone pushes with the lab token only ([0439748](https://github.com/lucawalz/vigil/commit/04397489f34e6b284d59417f7f0031756956b8a4))
- **eval**: Reject run records that name an unknown eval target ([fa22409](https://github.com/lucawalz/vigil/commit/fa22409b7b3d849dfa77b405c517355cc6e92b52))
- **eval**: Reject mixed-target run records in the step summary too ([5ee4868](https://github.com/lucawalz/vigil/commit/5ee486886fbab409475a07e1e1308d0104679366))
- **lab**: Disconnect hub clients that announce oversized frames ([b9afa6d](https://github.com/lucawalz/vigil/commit/b9afa6d62ca7a18d0646c0ce2fe409389a5ac410))
- **lab**: Confirm the installer key command reached the console ([627c89c](https://github.com/lucawalz/vigil/commit/627c89cb853ec02c4e25505e0d2c2dd7a22c2cf4))
- **mcp-servers**: Raise golang.org/x/net to v0.60.0 for http2 advisories ([f7f3a8e](https://github.com/lucawalz/vigil/commit/f7f3a8e5b29395d37ac2a8ac5c40ea1121b9d06c))
- **lab**: Report an agent that exits during start with its log ([62ae548](https://github.com/lucawalz/vigil/commit/62ae548a5ac189eddc985707dc167d75e93fd90c))
- **lab**: Keep lab ssh probes from asking for a password ([6e32f99](https://github.com/lucawalz/vigil/commit/6e32f99ae2f3c4f66a53d64819e98a179c49d730))
- **lab**: Check free memory only before the lab starts new machines ([127313f](https://github.com/lucawalz/vigil/commit/127313f8695262a64af04d9bc08a7a7bc3d80d55))
- **eval**: Fall back to the baseline branch for an empty eval branch ([b32432a](https://github.com/lucawalz/vigil/commit/b32432a7a7f80be630f134efb6bab42e69eff864))
- **lab**: Accept only whole github owner and name pairs for the repo ([5d38a88](https://github.com/lucawalz/vigil/commit/5d38a8865940d388c54302a4b4202501dd3d3439))
- **lab**: Create the lab state directory private from the first moment ([f471a92](https://github.com/lucawalz/vigil/commit/f471a926145eaaf18a959cce8af9654c67e5f32e))
- **nixos**: Name the lab hub interface by its mac address on every arch ([3d5723e](https://github.com/lucawalz/vigil/commit/3d5723e406df1930e529c755786bc3b5d9581b1b))

### Refactoring

- **common**: Keep the shared timeout constants free of inline comments ([74fbed7](https://github.com/lucawalz/vigil/commit/74fbed7c7134a65817f58e08d6b714e7f0323d53))
- **watchdog**: Share the revision match and os check with the orchestrator ([93c1885](https://github.com/lucawalz/vigil/commit/93c1885b73acf8432cb57690a8ef419be73ac4bd))
- **agents**: Name the vigil hosts in prompt examples and test fixtures ([d987824](https://github.com/lucawalz/vigil/commit/d987824c93266f124bd58863c7a5403bc5766e98))
- **nixos**: Share one hybrid disk layout driven by the disk device ([a546b66](https://github.com/lucawalz/vigil/commit/a546b66e5b49ed585e482f7ffca0393661038c0e))

### Documentation

- **github**: Link questions from the issue chooser to the q&a discussions ([e8ea619](https://github.com/lucawalz/vigil/commit/e8ea619289a56041b4333f6ca562a124625c23a7))
- **security**: State the response time and the supported release lines ([3ffc4b5](https://github.com/lucawalz/vigil/commit/3ffc4b5719e3ca3ef57bf6bb8c23b2fc7e444bf5))
- **contributing**: Describe the release notes source and the release comments ([2cf7941](https://github.com/lucawalz/vigil/commit/2cf7941e592c3efaee345a8b8cac375f3f950902))
- **infra**: Name the eval ruleset target in the github ui pattern form ([ccb2ffc](https://github.com/lucawalz/vigil/commit/ccb2ffccbdad515b674068ab3aae72ac482c2c0b))
- **contributing**: State the startup budget checks for the gate wait timeout ([eaaff46](https://github.com/lucawalz/vigil/commit/eaaff46918bdd62baf5b655b04792b314aba1048))
- **eval**: Describe the verified revert path of the k8s-rollback-1 scenario ([6a00fe3](https://github.com/lucawalz/vigil/commit/6a00fe3f0fe6c76d121e2f326003e65661898ea8))
- **eval**: List the gate ruleset as the only required repository setting ([1b6147b](https://github.com/lucawalz/vigil/commit/1b6147bf0d13163050093e19e84dd872b5a33583))
- **contributing**: Document the gate wait timeout environment variable ([e1fd3bf](https://github.com/lucawalz/vigil/commit/e1fd3bf49b20367e88df68504f6bb5d4dc5ac3dc))
- **infra**: Describe the eval harness app and its ruleset bypass ([3a572e2](https://github.com/lucawalz/vigil/commit/3a572e2ffbbf416c8568acde08303faf0a82988d))
- **infra**: Describe the github app identity for the agent ([1519b03](https://github.com/lucawalz/vigil/commit/1519b039aae1f0eee28f675150a99f709ccca9ff))
- **infra**: Document running the hetzner eval from a fork ([fe34482](https://github.com/lucawalz/vigil/commit/fe34482a07f28a621505db1c4d3dddf01a523121))
- **infra**: Describe the local lab, the vigil host names and campaign inputs ([52037f2](https://github.com/lucawalz/vigil/commit/52037f2736f8a46284f59ab954c554273284c5be))

### Testing

- **common**: Check the fencing toolset forwards every call argument unchanged ([7d7a9fc](https://github.com/lucawalz/vigil/commit/7d7a9fc5c565d1f0a2abfc1cb0b85d7636f7694d))
- **common**: Cover empty bodies, nonce placeholders and json fence values ([856c97c](https://github.com/lucawalz/vigil/commit/856c97cdd09e3e6b7e7c56e85415da36a08a9ee7))
- **common**: Type the toolset call helper in the fence tests ([c00adf8](https://github.com/lucawalz/vigil/commit/c00adf820324845b6182d8493a3badb5f71e9f05))
- **common**: Name the request parts helper after what it returns ([eed9535](https://github.com/lucawalz/vigil/commit/eed9535260d61485f14a5dbb8e8943516b0bdd44))
- **common**: Reuse the shared nonce constant in the fence tests ([1349299](https://github.com/lucawalz/vigil/commit/13492995fd66b46c8bc373e51b4d46700fbe8c78))

### Build

- **release**: Stage the lab package version in the release commit ([8638fa0](https://github.com/lucawalz/vigil/commit/8638fa0c6b31b169ebad26f9d983600273477f26))
- **release**: Match the git-mcp server version inside a const block ([a734afd](https://github.com/lucawalz/vigil/commit/a734afd5812461fc698dfecceb8635906b3f567a))
- **deps**: Raise certifi to drop the distrusted emsign roots ([2bcd8d1](https://github.com/lucawalz/vigil/commit/2bcd8d17b305128f9180f69efc77b86126e21585))
- **nixos**: Raise the nixpkgs pin to the current nixos-unstable ([5607144](https://github.com/lucawalz/vigil/commit/56071446294209c83942489e2c4ba6e718726134))
- **deps**: Raise aiohttp and mcp to their patched releases ([aafb70e](https://github.com/lucawalz/vigil/commit/aafb70e5927dd757ba768bc19b6f36fd71df6e05))
- **deps**: Raise pydantic-ai, fsspec and multidict to patched releases ([309ecba](https://github.com/lucawalz/vigil/commit/309ecbaa685b9a417692544a8fae0c5a9e0e84b1))

### CI

- Publish an openssf scorecard analysis and show its badge ([a2a612a](https://github.com/lucawalz/vigil/commit/a2a612a82887f378f7d6ffaca83b2a64ccce30a8))
- **release**: Comment the release on referenced issues and pull requests ([90a9329](https://github.com/lucawalz/vigil/commit/90a932949d34751f6af89f960f4b82c7ada7b446))
- **release**: Publish release notes copied from the changelog section ([5f9fc09](https://github.com/lucawalz/vigil/commit/5f9fc09b55c77dad8a96e9a008826c26c29619a4))
- Pass the hetzner token to the reusable snapshot build workflow ([aa0773e](https://github.com/lucawalz/vigil/commit/aa0773eece2a527a7211ecb01b78a9c9eeeec29c))
- **lab**: Give the smoke test's direct mcp calls their own timeout ([89fa308](https://github.com/lucawalz/vigil/commit/89fa30803a59debe463448ad9c43a3c3188e7186))
- **eval**: Give each scenario group time for three tries per incident ([83e7722](https://github.com/lucawalz/vigil/commit/83e77228b76ce0d4b0a960b5be05aad4035cfb3c))
- **eval**: Check the gate ruleset as the only repository setting ([3bbde1d](https://github.com/lucawalz/vigil/commit/3bbde1dc607ecc586b3f94eca2a770e73b9225bf))
- **eval**: Send the campaign dispatch inputs from the local act script ([4000dd3](https://github.com/lucawalz/vigil/commit/4000dd30b287923848755fc6b4848df80f549150))
- **lab**: Check k3s secrets encryption, audit log and kubeconfig mode ([bcf1c74](https://github.com/lucawalz/vigil/commit/bcf1c74d97468c35502c6f73b1e5eba961990c1c))
- **eval**: Use the eval harness app for cell branches and cleanup ([400349d](https://github.com/lucawalz/vigil/commit/400349d6d2481aa4ae8a31c202ab86220d341c64))
- **eval**: Mint github app tokens for each campaign job ([917bf1d](https://github.com/lucawalz/vigil/commit/917bf1d3f6a0133dd6ddb28aa5e0d28116fa5454))
- **eval**: Check fork repository settings before any campaign starts ([4140787](https://github.com/lucawalz/vigil/commit/4140787cd3e8a8f1ba94bacf5b440e4e56413e4f))
- **eval**: Validate agent manifests against the flux 2.9.6 schemas ([f39c9bf](https://github.com/lucawalz/vigil/commit/f39c9bfe0b6f31bf413084dc68e90f2773cb045c))
- Verify the golangci-lint config locally instead of per go job ([faa6122](https://github.com/lucawalz/vigil/commit/faa6122ca2d9258074d930e376a59da3c66821f1))
- **eval**: Delete agent branches of every campaign cell after aggregation ([abe864d](https://github.com/lucawalz/vigil/commit/abe864d556d340a6b83c35c9d2c5081e617c6bdf))
- Resolve the newest go 1.26 patch release in every go job ([9f538a4](https://github.com/lucawalz/vigil/commit/9f538a4e7c3b60cd8e2d41fc76e689c48d94a7d2))
- **eval**: Run campaign cells on per-cell branches against hetzner or the runner ([5bfe2d8](https://github.com/lucawalz/vigil/commit/5bfe2d8e9f88c6679f602740d7b98c7118b3c437))
- **lab**: Boot the lab on the runner and check health, rollback and alerts ([4a10579](https://github.com/lucawalz/vigil/commit/4a1057913b6636c8239dac21e9bc3e2d65ebd158))
- Keep pruning the uv cache in every cached job ([148b96d](https://github.com/lucawalz/vigil/commit/148b96da7d061800ee12787e0120f8e045c6a960))

### Dependencies

- **deps**: Bump python dependencies to their patched security releases ([6325e9b](https://github.com/lucawalz/vigil/commit/6325e9bf82b1886b682d508057914d8e12c64b03))
- **dependabot**: Update the major bump notice instead of repeating it ([dcb4ab3](https://github.com/lucawalz/vigil/commit/dcb4ab366c55bfc4a554499a1303f0ca5cb4e2ca))
- Bump DeterminateSystems/nix-installer-action from 22 to 23 (#1343) ([1aece7a](https://github.com/lucawalz/vigil/commit/1aece7a9451cec25dbc22482d9e5c75767d5b22f))
- Bump actions/checkout from 6 to 7 (#1341) ([dee1d31](https://github.com/lucawalz/vigil/commit/dee1d3144112dc18dd65b256c17da66b9e342734))
- Bump astral-sh/setup-uv from 8.2.0 to 10.2.0 (#1340) ([d59f5ea](https://github.com/lucawalz/vigil/commit/d59f5ea16c551f6fc0259315eda3837a8c8e0766))
- Bump actions/setup-go from 6 to 7 (#1339) ([2ab1494](https://github.com/lucawalz/vigil/commit/2ab14945cd8d1b66eea1929304eeeb5dfc5f851b))

### Miscellaneous

- Record go workspace checksums from the module graph ([f71a04f](https://github.com/lucawalz/vigil/commit/f71a04f502647662681842f908b96fc33ce7ca07))
- **nixos**: Drop the unused github ssh identity from host config ([eae60b5](https://github.com/lucawalz/vigil/commit/eae60b56c25b9bb83150cd1dba4ea5b05d09d55d))
- Record go workspace checksums from editor tooling ([3b209c3](https://github.com/lucawalz/vigil/commit/3b209c3af19100321e2a3729a38844ddfe4e9b0b))

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
