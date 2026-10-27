#!/usr/bin/env python3
"""Generate the exhaustive form list for the SuperFX decode check, one statement per 64-byte slot.
usage: gen_forms.py <out.asm> <out.stmts>
The statements are assembled with bass (`architecture snes.gsu`, an independent assembler used as
a black box), which emits the ALT/TO/WITH/FROM prefix bytes itself."""
import sys
BASE = 0x8000
SLOT = 64

def forms():
    f = []
    for m in "stop nop cache lsr rol alt1 alt2 alt3 plot swap color not merge sbk sex asr ror lob fmult hib getc getb rpix cmode div2 lmult getbh getbl getbs ramb romb loop".split():
        f.append(m)
    for r in range(16):
        f += [f"to r{r}", f"with r{r}", f"from r{r}", f"move r{r}, r{(r*5+3)%16}", f"moves r{r}, r{(r*7+1)%16}"]
        for m in "add adc sub sbc cmp and bic or xor mult umult".split():
            if m in ("and", "bic", "or", "xor") and r == 0:
                continue   # n = 0 is MERGE / HIB
            f.append(f"{m} r{r}")
        if r < 12:
            f += [f"stw (r{r})", f"ldw (r{r})", f"stb (r{r})", f"ldb (r{r})"]
        if r < 15:
            f += [f"inc r{r}", f"dec r{r}"]
        if 8 <= r <= 13:
            f += [f"jmp r{r}", f"ljmp r{r}"]
        for v in (0, 1, 0x7f, 0x80, 0xff, 0x55):
            f.append(f"ibt r{r}, #{v}")
        for v in (0, 0x1234, 0xffff, 0x8000):
            f.append(f"iwt r{r}, #{v}")
        for a in (0, 2, 0x20, 0x1fe):
            if a < 0x200:
                f += [f"lms r{r}, ({a})", f"sms ({a}), r{r}"]
        for a in (0x1234, 0x1235, 0, 0xfffe, 1):
            f += [f"lm r{r}, ({a})", f"sm ({a}), r{r}"]
    for n in range(16):
        for m in "add sub mult umult adc".split():
            f.append(f"{m} #{n}")
        if n:
            for m in "and bic or xor".split():
                f.append(f"{m} #{n}")
    for n in range(1, 5):
        f.append(f"link #{n}")
    for off in (-128, -2, 0, 1, 2, 0x10, 127):
        for m in "bra bge blt bne beq bpl bmi bcc bcs bvc bvs".split():
            f.append(f"{m} {BASE + 2 + off}")   # placeholder, fixed per slot below
    return f

def main():
    asm, stm = sys.argv[1:3]
    fs = forms()
    with open(asm, "w") as a, open(stm, "w") as s:
        a.write("architecture snes.gsu\n")
        for i, t in enumerate(fs):
            addr = BASE + i * SLOT
            if t[:3] in ("bra", "bge", "blt", "bne", "beq", "bpl", "bmi", "bcc", "bcs", "bvc", "bvs") and t[3] == " ":
                off = int(t.split()[1]) - (BASE + 2)
                t = f"{t.split()[0]} {addr + 2 + off}"
            a.write(f"origin {i*SLOT}\nbase {addr}\n {t}\nprint \"L \", origin(), \"\\n\"\n")
            s.write(t + "\n")
        a.write(f"origin {len(fs)*SLOT}\ndb 0\n")
main()
