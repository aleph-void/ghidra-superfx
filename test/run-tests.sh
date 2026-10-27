#!/usr/bin/env bash
# Runs every SuperFX check that needs no non-redistributable input.
#
#   GHIDRA_INSTALL_DIR=<Ghidra with this module linked into Ghidra/Processors/SuperFX> \
#     test/run-tests.sh [--real] [--n <random-cases>] <workdir>
#
# Needs: bass (byuu's assembler, ISC; `bass` on PATH or BASS=...), MAME's unidasm on PATH, python3,
# a JDK with javac for Ghidra (test/build-jar.sh builds lib/SuperFX.jar, the analyzer, first).
# Optional: wla-superfx + wlalink (WLA DX; WLA_DIR=<bin dir>) for the second-assembler check.
# --real fetches the DiscoC SNES demo payloads (pinned URL + SHA-256) and runs test/real-check.sh.
# Exit status 0 only if every step passes.
set -uo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(dirname "$HERE")
REAL=0; N=40000
while [[ ${1:-} == --* ]]; do
	case $1 in --real) REAL=1; shift ;; --n) N=$2; shift 2 ;; *) echo "unknown option $1" >&2; exit 2 ;; esac
done
W=$(mkdir -p "$1" && cd "$1" && pwd)
export TMPDIR=${TMPDIR:-$W}
export BASS=${BASS:-$(command -v bass || true)}
[[ -x $BASS ]] || { echo "bass not found (set BASS=)" >&2; exit 2; }
command -v unidasm >/dev/null || { echo "unidasm (MAME) not found on PATH" >&2; exit 2; }
fail=0
step() { echo "== $*"; }
ok() { "$@" || { echo "FAILED: $*"; fail=1; }; }

step "analyzer jar"
ok "$HERE/build-jar.sh"

step "spec compiles (sleigh -l: no unresolved pattern conflicts)"
out=$("$GHIDRA_INSTALL_DIR/support/sleigh" -l "$MOD/data/languages/superfx.slaspec" 2>&1)
if grep -q "ERROR" <<<"$out"; then echo "$out" | grep ERROR | head; echo "FAILED: superfx"; fail=1; else echo "superfx compiles, no conflicts"; fi
sz=$(stat -c %s "$MOD/data/languages/superfx.sla"); echo ".sla: $sz bytes"; ((sz < 16000000)) || { echo "FAILED: .sla too large"; fail=1; }

step "decode: every form bass can assemble (prefix chains included), round trip against the source statements"
ok "$HERE/forms-test.sh" "$W/forms"
if [[ -x ${WLA_DIR:-$HOME/.cache/ghidra-rare-scratch/tools/wla-dx/bin}/wla-superfx ]]; then
	step "second assembler: wla-superfx produces the same bytes as bass for every non-branch form"
	ok python3 "$HERE/cmp_wla.py" "$W/forms"
fi

step "decode: ALT1/ALT2/ALT3 x every opcode (forms bass lacks must fall back as the manual says)"
ok python3 "$HERE/alt_matrix.py" "$W/forms"

step "decode: $N random 12-byte strings against MAME unidasm (prefix-free instructions)"
ok python3 "$HERE/rand_diff.py" "$W/rand" "$N" 1

step "every constructor is reached"
ok "$HERE/every-entry.sh" "$W/ee"

step "p-code: hand-computed emulator cases"
ok python3 "$HERE/gen_emu.py" "$HERE/emu/cases.src" "$W/cases.txt"
ok cmp "$W/cases.txt" "$HERE/emu/cases.txt"
ok "$HERE/emu-test.sh" "$HERE/emu/cases.txt" "$W/emu"
tail -1 "$W/emu/emu.txt"

if ((REAL)); then
	step "real code (DiscoC compiler output)"
	ok "$HERE/real-check.sh" "$W/real"
fi
((fail)) && { echo "SOME CHECKS FAILED"; exit 1; }
echo "ALL CHECKS PASSED"
