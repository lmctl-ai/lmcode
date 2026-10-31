#!/usr/bin/env bash
# Source this locally, or execute in Actions (GITHUB_ENV/GITHUB_PATH persist it).
set -euo pipefail
ci_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
compiler_version="${COMPILER_VERSION:-$(cat "$ci_root/scripts/ci/compiler-version")}"
# A version or npm tag is data, not shell syntax; reject empty/option-like values.
[[ "$compiler_version" =~ ^[a-zA-Z0-9][a-zA-Z0-9.+_-]*$ ]] || { echo 'Invalid compiler version/tag' >&2; return 2 2>/dev/null || exit 2; }
compiler_prefix="$(mktemp -d "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/lmcode-compiler.XXXXXX")"
case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) compiler_prefix="$(cd "$compiler_prefix" && pwd -W)";; esac
npm install --prefix "$compiler_prefix" --no-audit --no-fund "@lmctl-ai/lmctl@$compiler_version"
export LMSCRIPT_BIN="$compiler_prefix/node_modules/.bin/lmscript"
export PATH="$compiler_prefix/node_modules/.bin:$PATH"
"$LMSCRIPT_BIN" --version
printf 'Compiler selector: %s\nPrivate prefix: %s\n' "$compiler_version" "$compiler_prefix"
if [[ -n "${GITHUB_ENV:-}" ]]; then printf 'LMSCRIPT_BIN=%s\n' "$LMSCRIPT_BIN" >> "$GITHUB_ENV"; fi
if [[ -n "${GITHUB_PATH:-}" ]]; then printf '%s\n' "$compiler_prefix/node_modules/.bin" >> "$GITHUB_PATH"; fi
