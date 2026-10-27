#!/usr/bin/env bash
# test/forms-test.sh <workdir>: every form bass can assemble, decoded by Ghidra with context propagation
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=$(mkdir -p "$1" && cd "$1" && pwd)
: "${BASS:=bass}"
python3 "$HERE/gen_forms.py" "$W/forms.asm" "$W/forms.stm"
"$BASS" -strict -o "$W/forms.bin" "$W/forms.asm" > "$W/forms.bout" 2>&1
python3 - "$W" <<'PY'
import sys
w = sys.argv[1]
data = open(f"{w}/forms.bin", "rb").read()
lens = [int(l.split()[1]) for l in open(f"{w}/forms.bout") if l.startswith("L ")]
with open(f"{w}/forms.hex", "w") as f:
    for i, l in enumerate(lens):
        f.write(data[i * 64:i * 64 + l - i * 64].hex() + "\n")
PY
"$HERE/dis-seq.sh" "$W/forms.hex" "$W/forms.dis"
python3 "$HERE/cmp_forms.py" "$W/forms.bin" "$W/forms.stm" "$W/forms.bout" "$W/forms.dis" "${2:-40}"
