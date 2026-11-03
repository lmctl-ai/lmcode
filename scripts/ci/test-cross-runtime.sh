#!/usr/bin/env bash
set -euo pipefail

# Lightweight contract test: the runner must reject an unknown runtime before
# touching a checkout, and a Go-shaped fake must receive both canonical
# vector paths and both sample sync calls.  This avoids building five SDKs in
# the lmcode repository's own shell tests.
root="$(cd "$(dirname "$0")/../.." && pwd)"
runner="${CROSS_RUNTIME_RUNNER:-$root/scripts/ci/cross-runtime.sh}"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/lmcode-cross-test.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/runtime/conformance/vectors" "$tmp/ref/conformance/vectors" "$tmp/ref/conformance/stdlib-vectors" "$tmp/sample/scripts" "$tmp/bin"
cat > "$tmp/compiler" <<'EOF'
#!/bin/sh
printf 'compiler %s\n' "$*" >> "$FAKE_LOG"
for argument in "$@"; do
  if [ "$argument" = --no-preflight ]; then echo 'retired standalone compiler option' >&2; exit 42; fi
done
exit 0
EOF
chmod +x "$tmp/compiler"
cat > "$tmp/bin/go" <<'EOF'
#!/bin/sh
printf '%s %s\n' "$(basename "$0")" "$*" >> "$FAKE_LOG"
exit 0
EOF
chmod +x "$tmp/bin/go"
cp "$tmp/bin/go" "$tmp/bin/cargo"
for name in sync-sdk.sh sync-suite.sh; do
  cat > "$tmp/sample/scripts/$name" <<EOF
#!/bin/sh
printf '$name %s\n' "\$1" >> "\$FAKE_LOG"
EOF
  chmod +x "$tmp/sample/scripts/$name"
done
cat > "$tmp/sample/test.sh" <<'EOF'
#!/bin/sh
printf 'sample-test native=%s\n' "${RUN_NATIVE:-0}" >> "$FAKE_LOG"
EOF
chmod +x "$tmp/sample/test.sh"
export FAKE_LOG="$tmp/log" PATH="$tmp/bin:$PATH" LMSCRIPT_BIN="$tmp/compiler"
if LANGUAGE=unknown RUNTIME_DIR="$tmp/runtime" REFERENCE_CPP_DIR="$tmp/ref" SAMPLE_DIR="$tmp/sample" "$runner" >/dev/null 2>&1; then
  echo 'FAIL: unsupported language was accepted' >&2
  exit 1
fi
test "$(LANGUAGE=go RUNTIME_DIR="$tmp/runtime" REFERENCE_CPP_DIR="$tmp/ref" SAMPLE_DIR="$tmp/sample" "$runner" | tail -1)" = 'PASS cross-runtime go'
grep -F "go run ./cmd/conformance $tmp/ref/conformance/vectors" "$FAKE_LOG" >/dev/null
grep -F "go run ./cmd/conformance $tmp/ref/conformance/stdlib-vectors" "$FAKE_LOG" >/dev/null
grep -F 'go mod edit -replace=github.com/lmctl-ai/lmcode-go=' "$FAKE_LOG" >/dev/null
grep -F 'compiler test.lms' "$FAKE_LOG" >/dev/null
grep -F 'sync-sdk.sh ' "$FAKE_LOG" >/dev/null
grep -F 'sync-suite.sh ' "$FAKE_LOG" >/dev/null
grep -F sample-test "$FAKE_LOG" >/dev/null
test "$(LANGUAGE=rust RUNTIME_DIR="$tmp/runtime" REFERENCE_CPP_DIR="$tmp/ref" SAMPLE_DIR="$tmp/sample" "$runner" | tail -1)" = 'PASS cross-runtime rust'
grep -F 'cargo run --release --manifest-path' "$FAKE_LOG" >/dev/null
echo 'PASS cross-runtime runner contract and refusal controls'

# The JVM adapter cannot use its POSIX discovery wrapper on Windows. Its
# existing native-host assertions must run rather than being skipped.
cp "$tmp/bin/go" "$tmp/bin/mvn"
cat > "$tmp/runtime/test.sh" <<'EOF'
#!/bin/sh
printf 'java-runtime-test\n' >> "$FAKE_LOG"
EOF
: > "$FAKE_LOG"
test "$(RUNNER_OS=Windows LANGUAGE=java RUNTIME_DIR="$tmp/runtime" REFERENCE_CPP_DIR="$tmp/ref" SAMPLE_DIR="$tmp/sample" "$runner" | tail -1)" = 'PASS cross-runtime java'
grep -F 'java-runtime-test' "$FAKE_LOG" >/dev/null
grep -F 'mvn -q' "$FAKE_LOG" >/dev/null
grep -F 'sample-test native=1' "$FAKE_LOG" >/dev/null
echo 'PASS Windows Java retains real native-host qualification'
