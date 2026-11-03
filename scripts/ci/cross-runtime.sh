#!/usr/bin/env bash
set -euo pipefail

# Run one runtime and its sample against the canonical C++ vectors.  The
# workflow supplies fresh checkouts; this script never mutates a source repo
# other than disposable sample checkouts (the JS sample is inside RUNTIME_DIR).
: "${LANGUAGE:?LANGUAGE is required (cpp|rust|go|java|csharp|js)}"
: "${RUNTIME_DIR:?RUNTIME_DIR is required}"
: "${REFERENCE_CPP_DIR:?REFERENCE_CPP_DIR is required}"
: "${SAMPLE_DIR:?SAMPLE_DIR is required}"
: "${LMSCRIPT_BIN:?LMSCRIPT_BIN must point at the npm-installed compiler}"

case "$LANGUAGE" in
  cpp|rust|go|java|csharp|js) ;;
  *) echo "unsupported LANGUAGE: $LANGUAGE" >&2; exit 2 ;;
esac
test -d "$RUNTIME_DIR/conformance/vectors" || { echo "runtime has no conformance vectors: $RUNTIME_DIR" >&2; exit 2; }
test -d "$REFERENCE_CPP_DIR/conformance/vectors" || { echo "reference vectors missing" >&2; exit 2; }
test -d "$REFERENCE_CPP_DIR/conformance/stdlib-vectors" || { echo "reference stdlib vectors missing" >&2; exit 2; }
# Windows command launchers do not carry a POSIX executable bit. The
# installer already executes --version; require their file, not Unix mode bits.
case "$LMSCRIPT_BIN" in
  *.cmd|*.bat) test -f "$LMSCRIPT_BIN" ;;
  *) test -x "$LMSCRIPT_BIN" ;;
esac || { echo "compiler launcher is missing or unusable: $LMSCRIPT_BIN" >&2; exit 2; }

run_runtime() {
  case "$LANGUAGE" in
    js)
      (cd "$RUNTIME_DIR"
        # The dependency-free SDK has no committed npm lock yet. Generate it
        # from the checked-out package, then use the clean-install contract.
        npm install --package-lock-only --ignore-scripts --no-audit --no-fund
        npm ci
        export LMCODE_CPP_DIR="$REFERENCE_CPP_DIR"
        node scripts/sync-std.mjs
        node scripts/sync-vectors.mjs
        npm test
        npm run mutation
        npm run conformance)
      ;;
    cpp) make -C "$RUNTIME_DIR" test conformance; make -C "$RUNTIME_DIR" build/conformance; "$RUNTIME_DIR/build/conformance" "$REFERENCE_CPP_DIR/conformance/vectors"; "$RUNTIME_DIR/build/conformance" "$REFERENCE_CPP_DIR/conformance/stdlib-vectors" ;;
    rust) (cd "$RUNTIME_DIR" && "$LMSCRIPT_BIN" --no-preflight test.lms); cargo run --release --manifest-path "$RUNTIME_DIR/Cargo.toml" --quiet -p dsl-conformance --bin dsl-conformance -- "$REFERENCE_CPP_DIR/conformance/vectors"; cargo run --release --manifest-path "$RUNTIME_DIR/Cargo.toml" --quiet -p dsl-conformance --bin dsl-conformance -- "$REFERENCE_CPP_DIR/conformance/stdlib-vectors" ;;
    go) (cd "$RUNTIME_DIR" && "$LMSCRIPT_BIN" --no-preflight test.lms && go run ./cmd/conformance "$REFERENCE_CPP_DIR/conformance/vectors" && go run ./cmd/conformance "$REFERENCE_CPP_DIR/conformance/stdlib-vectors") ;;
    java) (cd "$RUNTIME_DIR" && bash ./test.sh); (cd "$RUNTIME_DIR" && mvn -q -DskipTests -Dexec.classpathScope=test exec:java -Dexec.mainClass=io.lmctl.lmcode.ConformanceRunner -Dexec.args="$REFERENCE_CPP_DIR/conformance/vectors $REFERENCE_CPP_DIR/conformance/stdlib-vectors") ;;
    csharp) (cd "$RUNTIME_DIR" && "$LMSCRIPT_BIN" --no-preflight test.lms); dotnet run --project "$RUNTIME_DIR/conformance/LmCode.Conformance" -- "$REFERENCE_CPP_DIR/conformance/vectors"; dotnet run --project "$RUNTIME_DIR/conformance/LmCode.Conformance" -- "$REFERENCE_CPP_DIR/conformance/stdlib-vectors" ;;
  esac
}

sync_sample() {
  case "$LANGUAGE" in
    js) (cd "$RUNTIME_DIR" && LMCODE_CPP_DIR="$REFERENCE_CPP_DIR" node scripts/sync-sample-suite.mjs) ;;
    cpp) python3 "$SAMPLE_DIR/scripts/sync.py" sdk "$RUNTIME_DIR"; python3 "$SAMPLE_DIR/scripts/sync.py" suite "$REFERENCE_CPP_DIR" ;;
    rust|java) bash "$SAMPLE_DIR/scripts/sync-sdk.sh" "$RUNTIME_DIR"; bash "$SAMPLE_DIR/scripts/sync-suite.sh" "$REFERENCE_CPP_DIR" ;;
    go)
      # The Go sample has no vendored SDK sync script: its module pin is the
      # SDK contract. Overlay that pin with this disposable runtime checkout
      # so the cross-repo run tests the runtime checked out by this workflow.
      (cd "$SAMPLE_DIR" && go mod edit "-replace=github.com/lmctl-ai/lmcode-go=$RUNTIME_DIR")
      if [ -x "$SAMPLE_DIR/scripts/sync-sdk.sh" ]; then
        bash "$SAMPLE_DIR/scripts/sync-sdk.sh" "$RUNTIME_DIR"
      else
        echo "Go sample has no SDK sync script; its go.mod/go.sum pin is the SDK contract"
      fi
      bash "$SAMPLE_DIR/scripts/sync-suite.sh" "$REFERENCE_CPP_DIR"
      ;;
    csharp) python3 "$SAMPLE_DIR/scripts/sync.py" sdk "$RUNTIME_DIR"; python3 "$SAMPLE_DIR/scripts/sync.py" suite "$REFERENCE_CPP_DIR" ;;
  esac
}

echo "== runtime: $LANGUAGE"
run_runtime
echo "== sample sync: $LANGUAGE"
sync_sample
echo "== sample suite: $LANGUAGE"
if [[ "$LANGUAGE" == js ]]; then
  (cd "$RUNTIME_DIR" && npm run verify:pins && npm run sample-suite)
else
  (cd "$SAMPLE_DIR" && LMSCRIPT_BIN="$LMSCRIPT_BIN" LMSCRIPT_MIN=0 bash ./test.sh)
fi
echo "PASS cross-runtime $LANGUAGE"
