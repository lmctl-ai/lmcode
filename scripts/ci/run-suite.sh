#!/usr/bin/env bash
# Entry points below are extended as the spec/suite commits land; no skipped failures.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/../.."
: "${LMSCRIPT_BIN:?source scripts/ci/install-compiler.sh first}"
python3 scripts/ci/probe-compiler.py
python3 scripts/ci/check-reference-examples.py
python3 -m unittest discover -s scripts/ci/tests -p 'test_*.py' -v
bash scripts/ci/test-cross-runtime.sh
