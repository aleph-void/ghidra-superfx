#!/usr/bin/env python3
"""Random-byte decode differential: Ghidra (context-aware sweep) against MAME's superfx disassembler.
usage: rand_diff.py <workdir> <cases> <seed>
MAME's disassembler ignores the ALT/TO/WITH/FROM prefix state, so only instructions that follow no
prefix are compared (an instruction after a prefix, directly or through branches, is counted as
'prefix-dependent'). Known explained classes: BGE/BLT names exchanged (see GHIDRA-RARE.md)."""
import os, random, re, subprocess, sys
SLOT = 64
BASE = 0x8000
PRE = ("alt1", "alt2", "alt3", "to", "from", "with")

def mame_norm(addr, t):
    t = t.strip()
    m = re.match(r"(\w+)\s*(.*)", t)
    mn, ops = m.group(1).lower(), m.group(2).strip().replace(" ", "")
    if mn in ("bra", "bge", "blt", "bne", "beq", "bpl", "bmi", "bcc", "bcs", "bvc", "bvs"):
        return f"{mn} {addr + 2 + int(ops)}"
    if mn == "ibt":
        r, v = ops.split(",")
        return f"ibt {r.lower()},#{int(v, 16)}"
    if mn == "iwt":
        r, v = ops.split(",#")
        return f"iwt {r.lower()},#{int(v, 16)}"
    if mn == "link":
        return f"link#{ops}"
    return (mn + " " + ops.lower()).strip().replace(" #", "#")

def ghidra_norm(t):
    t = t.lower().strip().lstrip("_")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*", ",", t)
    t = t.replace(" #", "#")
    def num(m):
        s = m.group(0)
        return str(int(s, 16)) if s.startswith("0x") else s
    t = re.sub(r"0x[0-9a-f]+", num, t)
    return t

def main():
    w, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    here = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(w, exist_ok=True)
    rnd = random.Random(seed)
    cases = [bytes(rnd.randrange(256) for _ in range(12)) for _ in range(n)]
    with open(f"{w}/rd.hex", "w") as f:
        for c in cases:
            f.write(c.hex() + "\n")
    blob = b"".join(c + bytes(SLOT - len(c)) for c in cases)
    open(f"{w}/rd.bin", "wb").write(blob)
    subprocess.run([f"{here}/dis-seq.sh", f"{w}/rd.hex", f"{w}/rd.dis"], check=True)
    mame = subprocess.run(["unidasm", f"{w}/rd.bin", "-arch", "superfx", "-basepc", f"{BASE:x}", "-norawbytes"],
                          capture_output=True, text=True, check=True).stdout
    mm = {}
    for l in mame.splitlines():
        a, t = l.split(":", 1)
        mm[int(a, 16)] = t
    agree = dep = diff = 0
    classes = {}
    shown = 0
    for i, l in enumerate(open(f"{w}/rd.dis")):
        h, rest = l.rstrip("\n").split("|", 1)
        base = BASE + i * SLOT
        state = False   # inside a prefix chain
        for c in [x for x in rest.split(";") if x]:
            off, ln, txt = c.split(":", 2)
            off = int(off)
            g = ghidra_norm(txt)
            mn = g.split(" ")[0]
            m = mame_norm(base + off, mm[base + off]) if (base + off) in mm else None
            if state:
                dep += 1
            elif m is None:
                pass
            elif m == g:
                agree += 1
            else:
                # explained: BGE/BLT names exchanged
                key = None
                mm0 = m.split(" ")[0]
                if {mm0, mn} == {"bge", "blt"} and m.split(" ", 1)[1:] == g.split(" ", 1)[1:]:
                    key = "bge/blt name exchanged"
                if key:
                    classes[key] = classes.get(key, 0) + 1
                else:
                    diff += 1
                    if shown < 30:
                        print("DIFF", h, off, "ghidra:", g, "mame:", m)
                        shown += 1
            if mn in PRE:
                state = True
            elif mn[0] == "b" and len(mn) == 3 and mn not in ("bic",):
                pass   # branches keep the prefix state
            else:
                state = False
    print(f"random: {n} cases; agree {agree}, prefix-dependent (not compared) {dep}, explained {classes}, unexplained {diff}")
    sys.exit(1 if diff else 0)
if __name__ == "__main__":
    main()
