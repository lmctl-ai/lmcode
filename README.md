# lmcode

## CI and local verification

Pushes to main and pull requests run the suite on GitHub-hosted runners. No
self-hosted machine or globally installed lmctl is required. CI downloads
@lmctl-ai/lmctl with Node 24 into a fresh temporary npm prefix.

The compiler selector is the manual workflow input compiler_version, then the
repository variable LMCODE_COMPILER_VERSION, then scripts/ci/compiler-version
(currently 0.2.444, the published v6 baseline). To test a newer release or tag,
run the ci workflow manually and set compiler_version, for example staging.
A compiler that cannot satisfy the suite fails visibly; planned language
features must not be claimed as passing through skipped checks.

Run the same checks locally with Node 24, npm and Python 3:

```sh
source scripts/ci/install-compiler.sh
bash scripts/ci/run-suite.sh
```

To select a different published compiler:

```sh
COMPILER_VERSION=staging source scripts/ci/install-compiler.sh
bash scripts/ci/run-suite.sh
```
