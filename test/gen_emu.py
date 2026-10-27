#!/usr/bin/env python3
"""Expand test/emu/cases.src (asm lines) into test/emu/cases.txt (hex) with bass as the assembler.
usage: gen_emu.py <cases.src> <cases.txt>      (BASS=path to bass)
`asm <statements separated by ;>` is assembled at 0x8000, `asmat <hexaddr> <statements>` at that address."""
import os, subprocess, sys, tempfile
BASS = os.environ.get("BASS", "bass")

def assemble(addr, stmts):
    with tempfile.TemporaryDirectory() as d:
        src = f"{d}/a.asm"
        with open(src, "w") as f:
            f.write("architecture snes.gsu\norigin 0\nbase %d\n" % addr)
            for s in stmts.split(";"):
                f.write(" " + s.strip() + "\n")
        subprocess.run([BASS, "-strict", "-o", f"{d}/a.bin", src], check=True, capture_output=True)
        return open(f"{d}/a.bin", "rb").read().hex()

def main():
    with open(sys.argv[1]) as fi, open(sys.argv[2], "w") as fo:
        for line in fi:
            t = line.strip()
            if t.startswith("asm "):
                fo.write("code " + assemble(0x8000, t[4:]) + "\n")
            elif t.startswith("asmat "):
                _, a, rest = t.split(None, 2)
                fo.write(f"codeat {a} " + assemble(int(a, 16), rest) + "\n")
            else:
                fo.write(line)
main()
