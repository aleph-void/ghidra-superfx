#!/usr/bin/env python3
"""Compare Ghidra's analysed listing of a DiscoC payload with the compiler's own assembly listing.
usage: real_compare.py <name> <payload.bin> <listing.s> <ghidra.dis> <seeds.out>
The .s file lists every instruction with its offset (`; CODE+$xxxx`); Ghidra must have an instruction at
every offset with the same text (spelling normalised, branch labels resolved), and no instruction
that the listing does not have. `--seeds` mode writes the exported symbols' addresses."""
import re, sys
BASE = 0x706000   # replaced by the listing's __DISCO_CODE_START_ADDRESS in main()

def norm(t):
    t = t.lower().strip().lstrip("_")
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"\s*,\s*", ",", t)
    t = t.replace(" #", "#").replace(" (", "(")
    def num(m):
        s = m.group(0)
        if s.startswith("$"):
            return str(int(s[1:], 16))
        if s.startswith("0x"):
            return str(int(s, 16))
        return s
    t = re.sub(r"\$[0-9a-f]+|0x[0-9a-f]+", num, t)
    t = re.sub(r"^msbk$", "sbk", t)
    return t

def parse_listing(path):
    items = []        # (offset, text)
    labels = {}
    pending = []
    exports = set()
    for line in open(path):
        line = line.rstrip("\n")
        m = re.match(r"\s*\.export\s+(\S+)", line)
        if m:
            exports.add(m.group(1))
            continue
        m = re.match(r"^(\w+):\s*$", line)
        if m:
            pending.append(m.group(1))
            continue
        m = re.match(r"\s+(.*?)\s*;(?: explicit encoding ;)? CODE\+\$([0-9A-Fa-f]+)\s*$", line)
        if m:
            off = int(m.group(2), 16)
            for p in pending:
                labels[p] = off
            pending = []
            items.append((off, m.group(1).strip()))
    return items, labels, exports

def main():
    global BASE
    name, binf, lst, dis, mode = sys.argv[1:6]
    for line in open(lst):
        m = re.match(r"\.define __DISCO_CODE_START_ADDRESS \$([0-9A-Fa-f]+)", line)
        if m:
            BASE = int(m.group(1), 16)
            break
    if mode == "base":
        print("0x%x" % BASE)
        return
    label = sys.argv[6] if len(sys.argv) > 6 else name
    items, labels, exports = parse_listing(lst)
    if mode == "offsets":
        with open(dis, "w") as f:
            for off, t in items:
                f.write("%x\n" % (BASE + off))
        return
    if mode == "seeds":
        with open(dis, "w") as f:
            f.write("%x\n" % BASE)
            for e in sorted(exports):
                if e in labels:
                    f.write("%x\n" % (BASE + labels[e]))
        return
    data = open(binf, "rb").read()
    g = {}
    spans = []
    for l in open(dis):
        a, h, t = l.rstrip("\n").split(" ", 2)
        off = int(a, 16) - BASE
        g[off] = t
        spans.append((off, off + len(h) // 2))
    same = diff = missing = data_ok = 0
    bad = []
    PRE = ("alt1", "alt2", "alt3", "to", "from", "with")
    BR = ("bra", "bge", "blt", "bne", "beq", "bpl", "bmi", "bcc", "bcs", "bvc", "bvs")
    starts = sorted(g)
    claimed = set()
    prev_with = None      # register of a preceding WITH (so a following `to`/`from` is MOVE / MOVES)
    for k, (off, t) in enumerate(items):
        end = items[k + 1][0] if k + 1 < len(items) else off + 8
        chain = [o for o in starts if off <= o < end]
        claimed.update(chain)
        tl = t.lower()
        if t.startswith(".byte"):
            ok = any(s <= off < e for s, e in spans)
            data_ok += ok
            if not ok:
                missing += 1
                bad.append((off, t, "(not covered)"))
            prev_with = None
            continue
        m = re.match(r"(\w+)\s+(\w+)$", t)
        if m and m.group(1) in BR and m.group(2) in labels:
            t = "%s %d" % (m.group(1), BASE + labels[m.group(2)])
        want = norm(t)
        mm = re.match(r"(to|from) r(\d+)$", want)
        if prev_with is not None and mm:
            want = f"move r{mm.group(2)},r{prev_with}" if mm.group(1) == "to" else f"moves r{prev_with},r{mm.group(2)}"
        wm = re.match(r"with r(\d+)$", want)
        if wm:
            prev_with = int(wm.group(1))
        elif want.split(" ")[0] in BR or want.split(" ")[0] in ("alt1", "alt2", "alt3"):
            pass          # these keep the WITH state
        else:
            prev_with = None
        if not chain or chain[0] != off:
            missing += 1
            bad.append((off, t, "(no instruction)"))
            continue
        texts = [norm(g[o]) for o in chain]
        last = texts[-1]
        pre_ok = all(x.split(" ")[0] in PRE for x in texts[:-1])
        # a branch line includes its delay-slot byte? no: the slot is the next listing line
        if last == want and pre_ok:
            same += 1
        elif want.split(" ")[0] in PRE and texts == [want]:
            same += 1
        else:
            diff += 1
            bad.append((off, t, " ; ".join(g[o] for o in chain)))
    extra = [o for o in g if o not in claimed]
    # classify the lines Ghidra has no instruction for: the byte after STOP (fetched, never executed;
    # execution resumes two bytes on), and dead code behind an unconditional jump and its slot
    pad = dead = 0
    explained = set()
    for k, (off, t) in enumerate(items):
        if off in g or t.startswith(".byte"):
            continue
        p1 = items[k - 1][1] if k else ""
        p2 = items[k - 2][1] if k > 1 else ""
        if p1.startswith("stop") and t == "nop":
            pad += 1
            explained.add(off)
        elif (p2.startswith(("iwt r15", "bra ", "jmp ")) and p1 == "nop") or \
                (items[k - 1][0] in explained and not p1.startswith("stop")) or \
                (p1.startswith(("iwt r15", "bra ", "jmp ")) and False):
            dead += 1
            explained.add(off)
    unexplained_missing = missing - pad - dead
    print(f"{label}: listing {len(items)} lines: {same} identical, {diff} different, {missing} missing "
          f"({pad} byte after STOP, {dead} dead code after an unconditional jump, {unexplained_missing} unexplained), "
          f"{data_ok} .byte lines covered; Ghidra-only instructions {len(extra)}")
    for b in [x for x in bad if x[0] not in explained][:15]:
        print("  DIFF %04x listing: %s  ghidra: %s" % b)
    for o in sorted(extra)[:10]:
        print("  EXTRA %04x ghidra: %s" % (o, g[o]))
    sys.exit(1 if (diff or unexplained_missing or extra) else 0)
main()
