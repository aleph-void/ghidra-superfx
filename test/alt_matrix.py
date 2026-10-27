#!/usr/bin/env python3
"""ALT matrix: every (ALT1/ALT2/ALT3, opcode) pair. Pairs bass has a form for are covered by forms-test;
for the others, the ALT prefix must be ignored (ALT3 falls back to the ALT1 form, then to no prefix,
per fullsnes) so the instruction must decode like MAME's (prefix-blind) text, or like the ALT1 form.
usage: alt_matrix.py <workdir>   (needs forms-test.sh to have run in <workdir>)"""
import os, random, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rand_diff import mame_norm, ghidra_norm   # noqa (rand_diff runs main on import guard below)

BASE = 0x8000
SLOT = 64

def main():
    w = sys.argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    have = set()
    stm = [l.rstrip("\n") for l in open(f"{w}/forms.stm")]
    hx = [l.strip() for l in open(f"{w}/forms.hex")]
    for s, h in zip(stm, hx):
        b = bytes.fromhex(h)
        if len(b) >= 2 and b[0] in (0x3d, 0x3e, 0x3f) and not s.startswith("alt"):
            have.add((b[0] - 0x3c, b[1]))
    rnd = random.Random(7)
    cases = []
    for alt in (1, 2, 3):
        for op in range(256):
            for k in range(2):
                cases.append((alt, op, bytes([0x3c + alt, op, rnd.randrange(256), rnd.randrange(256)])))
    # references: the ALT1 forms and the plain forms
    ref = []
    for alt, op, b in cases:
        ref.append(b[1:].hex())
    with open(f"{w}/am.hex", "w") as f:
        for _, _, b in cases:
            f.write(b.hex() + "\n")
        for r in ref:
            f.write(r + "\n")
        for alt, op, b in cases:
            f.write((bytes([0x3d]) + b[1:]).hex() + "\n")
    subprocess.run([f"{here}/dis-seq.sh", f"{w}/am.hex", f"{w}/am.dis"], check=True)
    lines = [l.rstrip("\n").split("|", 1) for l in open(f"{w}/am.dis")]
    n = len(cases)
    def items(i):
        return [c.split(":", 2) for c in lines[i][1].split(";") if c]
    # MAME text for the plain bytes
    blob = b"".join(bytes.fromhex(r) + bytes(SLOT - len(bytes.fromhex(r))) for r in ref)
    open(f"{w}/am.bin", "wb").write(blob)
    mame = subprocess.run(["unidasm", f"{w}/am.bin", "-arch", "superfx", "-basepc", f"{BASE:x}", "-norawbytes"],
                          capture_output=True, text=True, check=True).stdout
    mm = {}
    for l in mame.splitlines():
        a, t = l.split(":", 1)
        mm[int(a, 16)] = t
    ok = covered = bad = skipped = 0
    for i, (alt, op, b) in enumerate(cases):
        it = items(i)
        got = ghidra_norm(it[1][2]) if len(it) > 1 else None
        if (alt, op) in have:
            covered += 1
            continue
        if alt == 3 and (1, op) in have:
            it1 = items(2 * n + i)
            exp = ghidra_norm(it1[1][2]) if len(it1) > 1 else None
            why = "ALT3 -> ALT1 form"
        else:
            m = mm.get(BASE + i * SLOT)
            exp = mame_norm(BASE + i * SLOT + 1, m) if m else None
            why = "ALT ignored"
            # MAME names for 06/07 are exchanged
            if exp and got and exp.split(" ")[0] in ("bge", "blt") and got.split(" ")[0] in ("bge", "blt"):
                exp = got.split(" ")[0] + " " + exp.split(" ", 1)[1]
        if got is None and exp and exp.split(" ")[0][0] == "b":
            skipped += 1     # a branch whose target conflicts with the case bytes: no second item
        elif exp == got:
            ok += 1
        else:
            bad += 1
            if bad < 25:
                print("DIFF", alt, f"{op:02x}", "ghidra:", got, "expected:", exp, "(" + why + ")")
    print(f"alt matrix: {len(cases)} cases ({covered} covered by the bass forms), {ok} fall-back cases agree, {skipped} skipped (branch targets inside the slot), {bad} differ")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main()
