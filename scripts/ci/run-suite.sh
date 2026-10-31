#!/usr/bin/env bash
# Entry points below are extended as the spec/suite commits land; no skipped failures.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${LMSCRIPT_BIN:?source scripts/ci/install-compiler.sh first}"
python3 scripts/ci/probe-compiler.py
python3 -m unittest discover -s scripts/ci/tests -p 'test_*.py' -v
