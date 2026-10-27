#!/usr/bin/env bash
# Every-entry test: test/every-entry.sh <workdir>. Decodes (alt, b, sreg, dreg, opcode) combinations and
# reports the SLEIGH constructors (all tables) that were never used.
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd)
python3 - "$W/ee.in" <<'PY'
import sys
with open(sys.argv[1], 'w') as f:
    for alt in range(4):
        for b in range(2):
            for k in range(16):
                s, d = k, (k * 7 + 3) % 16
                for op in range(256):
                    f.write(f"{op:02x}1234 {alt} {b} {s} {d}\n{op:02x}1335 {alt} {b} {s} {d}\n")
PY
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/sfx-ee.XXXXXX"); trap 'rm -rf "$PROJ"' EXIT
head -c 64 /dev/zero > "$PROJ/zero.bin"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" -loader BinaryLoader \
	-loader-baseAddr 0x8000 -processor SuperFX:LE:24:default -noanalysis -scriptPath "$HERE" \
	-postScript EveryEntry.java "$W/ee.in" "$W/ee.out" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $W/ee.out ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
cat "$W/ee.out"
grep -q " 0 not reached" "$W/ee.out"
