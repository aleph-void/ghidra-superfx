#!/usr/bin/env python3
"""Compare the decode of the bass-assembled forms with the source statements.
usage: cmp_forms.py <forms.bin> <forms.stm> <bass-stdout> <dis-seq-output>
The Ghidra chain for a statement must be: zero or more prefix instructions (ALT1/2/3, TO, FROM, WITH)
followed by the statement itself (spelling normalised); the chain must also cover exactly the bytes bass emitted."""
import re, sys
SLOT = 64
PREFIX = ("alt1", "alt2", "alt3", "to", "from", "with")

def norm(t):
    t = t.lower().strip()
    t = re.sub(r"^_", "", t)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*", ",", t)
    t = t.replace(" #", "#").replace(" (", "(")
    def num(m):
        s = m.group(0)
        neg = s.startswith("-")
        s2 = s.lstrip("-")
        v = int(s2, 16) if s2.startswith("0x") else (int(s2[1:], 16) if s2.startswith("$") else int(s2))
        return str(-v if neg else v)
    t = re.sub(r"-?(0x[0-9a-f]+|\$[0-9a-f]+|\d+)", num, t)
    return t

def main():
    binf, stm, bout, dis = sys.argv[1:5]
    data = open(binf, "rb").read()
    stmts = [l.rstrip("\n") for l in open(stm)]
    lens = [int(x.split()[1]) for x in open(bout) if x.startswith("L ")]
    lens = [lens[i] - i * SLOT for i in range(len(stmts))]
    out = {}
    for l in open(dis):
        h, rest = l.rstrip("\n").split("|", 1)
        out[h] = rest
    n = ok = 0
    bad = []
    for i, s in enumerate(stmts):
        raw = data[i * SLOT:i * SLOT + lens[i]]
        key = raw.hex()
        # DisSeq prints instructions starting inside the case bytes: the case is exactly the bass bytes
        chain = [c for c in out.get(key, "").split(";") if c]
        n += 1
        if not chain:
            bad.append((s, key, "no output"))
            continue
        items = []
        total = 0
        for c in chain:
            off, ln, txt = c.split(":", 2)
            items.append(txt)
            total += int(ln)
        want = norm(s)
        got = norm(items[-1])
        pre = [norm(x).split(" ")[0] for x in items[:-1]]
        good = got == want and all(p in PREFIX for p in pre)
        # delay-slot branches: the chain's last item may be a slot; handled by generator (no slot used)
        if total != len(raw) and not good:
            pass
        if good and total == len(raw):
            ok += 1
        else:
            bad.append((s, key, " ; ".join(items)))
    print(f"forms: {n}, agree {ok}, different {len(bad)}")
    for b in bad[:int(sys.argv[5]) if len(sys.argv) > 5 else 40]:
        print("DIFF", *b, sep="\t")
    sys.exit(1 if bad else 0)
main()
