#!/usr/bin/env python3
"""Second assembler: assemble the non-branch statements of forms.stm with wla-superfx (WLA DX, GPL, run as a
black box) and compare the bytes with bass's.   usage: cmp_wla.py <workdir>   (WLA_DIR with wla-superfx, wlalink)"""
import os, re, subprocess, sys
w = sys.argv[1]
wla = os.environ.get("WLA_DIR", os.path.expanduser("~/.cache/ghidra-rare-scratch/tools/wla-dx/bin"))
stm = [l.rstrip("\n") for l in open(f"{w}/forms.stm")]
hx = [l.strip() for l in open(f"{w}/forms.hex")]
BR = ("bra", "bge", "blt", "bne", "beq", "bpl", "bmi", "bcc", "bcs", "bvc", "bvs")
def wsyntax(t):
    t = re.sub(r"(?<![\w$])(\d+)(?![\w])", lambda m: "$%x" % int(m.group(1)) if not t.startswith(("link", "to", "with", "from")) else m.group(1), t)
    return t
items = [(s, h) for s, h in zip(stm, hx) if s.split()[0] not in BR]
res = {"ok": 0, "bad": [], "unsupported": []}
with open(f"{w}/wla.s", "w") as f:
    f.write(".memorymap\n slotsize $8000\n defaultslot 0\n slot 0 $0000\n.endme\n.rombanksize $8000\n.rombanks 1\n.bank 0 slot 0\n.org 0\n")
    for i, (s, h) in enumerate(items):
        f.write(f".section \"s{i}\" force\n.db 'S'\n {wsyntax(s)}\n.db 'E'\n.ends\n")
r = subprocess.run([f"{wla}/wla-superfx", "-i", "-o", f"{w}/wla.o", f"{w}/wla.s"], capture_output=True, text=True)
lines = (r.stdout + r.stderr).splitlines()
errs = {}
for l in lines:
    m = re.match(r"wla.s:(\d+):", l)
    if m and "ERROR" in l.upper():
        errs[int(m.group(1))] = l
if errs:
    # drop unsupported statements and retry
    bad_idx = set()
    for ln in errs:
        i = (ln - 9) // 5 + 0 if ln >= 9 else -1
    # recompute exactly: header is 8 lines, each item has 5 lines, the statement is the 3rd
    for ln in errs:
        i = (ln - 9) // 5
        bad_idx.add(i)
    res["unsupported"] = sorted({items[i][0].split()[0] for i in bad_idx if 0 <= i < len(items)})
    items = [it for i, it in enumerate(items) if i not in bad_idx]
    with open(f"{w}/wla.s", "w") as f:
        f.write(".memorymap\n slotsize $8000\n defaultslot 0\n slot 0 $0000\n.endme\n.rombanksize $8000\n.rombanks 1\n.bank 0 slot 0\n.org 0\n")
        for i, (s, h) in enumerate(items):
            f.write(f".section \"s{i}\" force\n.db 'S'\n {wsyntax(s)}\n.db 'E'\n.ends\n")
    r = subprocess.run([f"{wla}/wla-superfx", "-i", "-o", f"{w}/wla.o", f"{w}/wla.s"], capture_output=True, text=True)
open(f"{w}/wla.link", "w").write("[objects]\nwla.o\n")
r2 = subprocess.run([f"{wla}/wlalink", "-r", "wla.link", "wla.rom"], capture_output=True, text=True, cwd=w)
rom = open(f"{w}/wla.rom", "rb").read()
# split by markers 'S'(0x53) ... 'E'(0x45): sections are consecutive with .org 0 force -> parse sequentially
pos = 0
for s, h in items:
    assert rom[pos] == 0x53, (s, pos)
    end = pos + 1
    while True:
        # the statement bytes are exactly the bass bytes when they agree; find the 'E' marker after len(h)/2 bytes
        break
    n = len(h) // 2
    got = rom[pos + 1:pos + 1 + n].hex()
    if rom[pos + 1 + n] != 0x45:
        res["bad"].append((s, h, rom[pos + 1:pos + 12].hex()))
        # resync to next 'S'
        nxt = rom.find(b"E", pos + 1)
        pos = nxt + 1
        continue
    if got == h:
        res["ok"] += 1
    else:
        res["bad"].append((s, h, got))
    pos = pos + n + 2
print(f"wla-superfx vs bass: {len(items)} statements, {res['ok']} identical bytes, {len(res['bad'])} different; unsupported by wla: {res['unsupported']}")
for b in res["bad"][:30]:
    print("DIFF", *b, sep="\t")
