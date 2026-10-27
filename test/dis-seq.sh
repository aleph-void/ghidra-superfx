#!/usr/bin/env bash
# test/dis-seq.sh <cases.txt> <out.txt>   (GHIDRA_INSTALL_DIR set)
# Decodes each hex string with real disassembly (context propagation). Output: <hex>|off:len:text;...
set -euo pipefail
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}"
HERE=$(cd "$(dirname "$0")" && pwd)
IN=$(readlink -f "$1"); OUT=$(readlink -m "$2")
N=$(grep -c . "$IN")
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/sfx-dis.XXXXXX"); trap 'rm -rf "$PROJ"' EXIT
head -c $((N * 64 + 64)) /dev/zero > "$PROJ/zero.bin"
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" -loader BinaryLoader \
	-loader-baseAddr 0x8000 -processor SuperFX:LE:24:default -noanalysis -scriptPath "$HERE" \
	-postScript DisSeq.java "$IN" "$OUT" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $OUT ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
