#!/usr/bin/env bash
# Entry points below are extended as the spec/suite commits land; no skipped failures.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/../.."
: "${LMSCRIPT_BIN:?source scripts/ci/install-compiler.sh first}"
python3 scripts/ci/probe-compiler.py
python3 scripts/ci/check-reference-examples.py
python3 scripts/ci/check-tutorial.py --sample-root "${LMCODE_SAMPLE:?set LMCODE_SAMPLE to the built C++ sample checkout}"
python3 -m unittest discover -s scripts/ci/tests -p 'test_*.py' -v
python3 scripts/ci/check-invocation-envelopes.py
python3 -m unittest discover -s tests/grammar -p 'test_*.py' -v
bash scripts/ci/test-cross-runtime.sh
upstream_status=0
python3 tests/grammar/check_corpus.py --cpp-root "${LMCODE_CPP:?set LMCODE_CPP to the reference checkout}" --lmok-root "${LMCODE_LMOK:?set LMCODE_LMOK to the lmok checkout}" || upstream_status=1
python3 scripts/gen-std-signatures.py "$LMCODE_CPP/std/lmcode-std.schema.json" --docs "$LMCODE_CPP/std/lmcode-std.docs.json" --check || upstream_status=1
exit "$upstream_status"
