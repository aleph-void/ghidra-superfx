#!/usr/bin/env bash
# Real-code check: the DiscoC SNES demo payloads (compiler output) imported headless with full
# auto-analysis (functions seeded at the exported symbols, because GSU calls are `iwt r15`), every
# function decompiled, and the analysed listing compared with the compiler's own assembly listing.
#   GHIDRA_INSTALL_DIR=... test/real-check.sh <workdir>
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd)
S=$("$HERE/fetch-samples.sh" "$W/samples")
rc=0
for c in triangle-O2 scaling-O2 scaling-Os rotation-O2 rotation-Os shapes-O2 shapes-Os gem-O2 gem-Os; do
	P="$W/$c"
	B=$(python3 "$HERE/real/real_compare.py" "$c" "$S/$c/triangle.bin" "$S/$c/triangle.s" - base)
	python3 "$HERE/real/real_compare.py" "$c" "$S/$c/triangle.bin" "$S/$c/triangle.s" "$P.offsets" offsets
	python3 "$HERE/real/real_compare.py" "$c" "$S/$c/triangle.bin" "$S/$c/triangle.s" "$P.seeds" seeds
	PROJ=$(mktemp -d "${TMPDIR:-/tmp}/sfx-real.XXXXXX")
	"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$S/$c/triangle.bin" -loader BinaryLoader \
		-loader-baseAddr "$B" -processor SuperFX:LE:24:default -scriptPath "$HERE" \
		-preScript Seed.java "$P.seeds" -postScript RealCheck.java "$P" 60 \
		-postScript ForceDis.java "$P.offsets" -postScript RealCheck.java "$P.full" 60 nodecomp -deleteProject >"$PROJ/log.txt" 2>&1 \
		|| { tail -40 "$PROJ/log.txt" >&2; rm -rf "$PROJ"; exit 1; }
	rm -rf "$PROJ"
	grep -v "^bookmark" "$P.summary"
	echo "-- auto-analysis only (what is reachable by flow, LINK calls and constant-loaded JMP/LOOP targets)"
	python3 "$HERE/real/real_compare.py" "$c" "$S/$c/triangle.bin" "$S/$c/triangle.s" "$P.dis" cmp "$c reached" || true
	echo "-- plus a disassembly start at every listed offset nothing reached (decode check of the whole image)"
	python3 "$HERE/real/real_compare.py" "$c" "$S/$c/triangle.bin" "$S/$c/triangle.s" "$P.full.dis" cmp "$c full" || rc=1
done
exit $rc
