# SuperFX (GSU): verification notes (Ghidra-Rare)

Language `SuperFX:LE:24:default` (see README.md). Provenance and the list of changes are in
[CREDITS.md](CREDITS.md). Everything below is reproduced by

    GHIDRA_INSTALL_DIR=<Ghidra with this directory linked into Ghidra/Processors/SuperFX> \
        BASS=<bass> test/run-tests.sh [--real] [--n <random-cases>] <workdir>

(needs `bass`, MAME's `unidasm`, python3, a JDK with `javac`; `wla-superfx`/`wlalink` from WLA DX
10.5 optionally, `WLA_DIR=<bin dir>`). `--real` fetches the DiscoC SNES demo payloads (pinned URL
+ SHA-256, never committed) and runs `test/real-check.sh`. The suite was run against Ghidra 12.1.4;
the release zips are built for 12.1.3, 12.1.4 and 12.2 and the spec compiles with each version's
SLEIGH compiler.

## Results

| Area | Result |
|---|---|
| Build | The spec compiles on 12.1.3, 12.1.4 and 12.2; `sleigh -l` reports no pattern conflicts; `.sla` 13 KB (upstream's committed `.sla` is no longer tracked) |
| Decode vs bass | 1,043 statements (every mnemonic and operand form bass has: all 16 registers, immediates, the 11 branches at 7 offsets, LMS/SMS/LM/SM with even and odd addresses, MOVE/MOVES, explicit prefixes), each assembled by bass (which writes the ALT/TO/FROM/WITH prefix bytes itself) and decoded by Ghidra with context propagation: 1,043 agree (the prefix chain plus the instruction equals the statement), 0 differ |
| Decode vs WLA DX | `wla-superfx` assembles the 966 non-branch statements to exactly the bytes bass produced (966/966): two independent assemblers agree with each other, so the check above stands on both |
| Decode vs MAME | 40,000 random 12-byte strings (seed 1): 274,091 prefix-free instructions compared, all agree except 1,961 whose branch names differ (below); 60,094 instructions that follow a prefix are not compared because MAME ignores the prefix state; 0 unexplained |
| ALT matrix | ALT1/ALT2/ALT3 x all 256 opcodes (1,536 cases): 674 are forms bass has (covered above); in the other 862 the prefix must be ignored (ALT3: fall back to the ALT1 form first), checked against MAME's plain decoding or Ghidra's own ALT1 decoding: 857 agree, 5 skipped (the branch target falls inside the test slot), 0 differ |
| Every constructor reached | 132/132 (65,536 decodes: every opcode x alt x b x sreg/dreg) |
| Semantics | Registers read through Rs and written through Rd, flags, memory, branches with delay slots, LOOP/LINK/JMP/LJMP, PLOT/RPIX, COLOR/POR in p-code. 106 hand-computed emulator cases (EmulatorHelper), 0 failures; one deliberately wrong expectation is reported as failing |
| Real code | DiscoC v0.2.0 SNES demo payloads (compiler output, GPL-3.0; 9 images: triangle, scaling, rotation, shapes, gem-chess at -O2 and -Os; 61,742 listed lines): 0 different, 0 unexplained misses, 0 instructions the listing lacks; all 64 functions decompile; see below |

Real code, per image (`listing` = lines of the compiler's own assembly listing; every line must be
an instruction in Ghidra at the same offset with the same text, branch labels resolved; a prefix
chain counts as one line):

| Image | Load address | Listing lines | Auto-analysis | Whole image (second pass) | Decompile |
|---|---|---|---|---|---|
| triangle-O2 | 0x706000 | 187 | 182 identical, 4 byte after STOP, 0 dead code, 0 different, 0 unexplained | 186 identical + 1 `.byte` covered, 0 different, 0 missing | 2 functions, 2 ok / 0 failed / 0 timeouts |
| scaling-O2 | 0x706000 | 462 | 454 identical, 5 byte after STOP, 2 dead code, 0 different, 0 unexplained | 461 identical + 1 `.byte` covered, 0 different, 0 missing | 2 functions, 2 ok / 0 failed / 0 timeouts |
| scaling-Os | 0x706000 | 394 | 390 identical, 3 byte after STOP, 0 dead code, 0 different, 0 unexplained | 393 identical + 1 `.byte` covered, 0 different, 0 missing | 2 functions, 2 ok / 0 failed / 0 timeouts |
| rotation-O2 | 0x706000 | 1,979 | 1,953 identical, 10 byte after STOP, 2 dead code, 0 different, 0 unexplained | 1,965 identical + 14 `.byte` covered, 0 different, 0 missing | 4 functions, 4 ok / 0 failed / 0 timeouts |
| rotation-Os | 0x706000 | 1,854 | 1,832 identical, 8 byte after STOP, 0 dead code, 0 different, 0 unexplained | 1,840 identical + 14 `.byte` covered, 0 different, 0 missing | 4 functions, 4 ok / 0 failed / 0 timeouts |
| shapes-O2 | 0x708000 | 7,962 | 7,857 identical, 77 byte after STOP, 0 dead code, 0 different, 0 unexplained | 7,934 identical + 28 `.byte` covered, 0 different, 0 missing | 7 functions, 7 ok / 0 failed / 0 timeouts |
| shapes-Os | 0x708000 | 7,636 | 7,527 identical, 81 byte after STOP, 0 dead code, 0 different, 0 unexplained | 7,608 identical + 28 `.byte` covered, 0 different, 0 missing | 7 functions, 7 ok / 0 failed / 0 timeouts |
| gem-O2 | 0x706000 | 20,834 | 20,466 identical, 278 byte after STOP, 0 dead code, 0 different, 0 unexplained | 20,744 identical + 90 `.byte` covered, 0 different, 0 missing | 18 functions, 18 ok / 0 failed / 0 timeouts |
| gem-Os | 0x706000 | 20,434 | 20,063 identical, 281 byte after STOP, 0 dead code, 0 different, 0 unexplained | 20,344 identical + 90 `.byte` covered, 0 different, 0 missing | 18 functions, 18 ok / 0 failed / 0 timeouts |

"Auto-analysis" is the headless import with the language's analyzer (functions are seeded at the
payload's entry and the exported symbols; the rest is found by flow, the `LINK` call idiom and
`IWT`-loaded `JMP`/`LOOP` targets). Every line it does not reach is either the byte after a `STOP` (the
hardware fetches it but never executes it; execution resumes two bytes on) or dead code behind an
unconditional jump and its slot (4 lines). The second pass starts a
disassembly at every listed offset nothing reached, so the whole image is compared; there, every
line is identical, no instruction exists that the listing does not have, and each `.byte` line
(an encoding the compiler's assembler has no mnemonic for, for example `ALT1` + `$9F`) lies inside a
Ghidra instruction. Every function decompiles (0 failures, 0 timeouts); the "warnings" are the
decompiler's own "removing unreachable block" notes.

## Method

- **Decode.** Two assemblers (bass `architecture snes.gsu`, WLA DX `wla-superfx`) are run as black
  boxes: the statement list is assembled and the bytes are decoded by Ghidra with real disassembly
  (so `globalset` context reaches the next instruction); the Ghidra text must reproduce the
  statement. MAME's `unidasm -arch superfx` is prefix-blind, so it is used on random bytes for the
  instructions that follow no prefix and, with the ALT matrix, for the opcodes where a prefix has no
  effect. Neither bass nor MAME was read; their source was not consulted.
- **Semantics.** The emulator cases (`test/emu/cases.src`, assembled with bass, expectations worked
  out from the fullsnes GSU documentation) cover: Sreg/Dreg selection (FROM/TO/WITH, prefixes reset
  after the instruction, kept across a branch), ADD/ADC/SUB/SBC/CMP with carry and overflow,
  AND/BIC/OR/XOR/NOT, LSR/ASR/ROL/ROR/DIV2, SWAP/SEX/LOB/HIB/MERGE, INC/DEC, MULT/UMULT/FMULT/
  LMULT, IBT/IWT/MOVE/MOVES, LDW/STW (even and odd addresses), LDB/STB, LMS/SMS/LM/SM, RAMB, SBK,
  GETB/GETBH/GETBL/GETBS/GETC, ROMB/COLOR/CMODE, all 11 branches taken and not taken (the delay slot
  runs in both), backward branch, LOOP, JMP, LJMP (PBR, CBR), IWT/ALU writes to R15, LINK + call +
  `JMP R11` return, STOP, PLOT in 4/16/256 colours, OBJ and 160-pixel layouts, SCBR, dither,
  transparency, RPIX, and the COLOR POR options.
- **Real code.** `test/fetch-samples.sh` fetches the DiscoC v0.2.0 demo bundle (SHA-256 pinned);
  `test/real-check.sh` imports each payload at its link address and compares with the listing.

## Confirmed reference-tool defects

- MAME `superfx` names opcode `06` `BLT` and `07` `BGE`. The hardware pattern (each pair of branches
  tests a flag clear, then set: BNE/BEQ, BPL/BMI, BCC/BCS, BVC/BVS) and fullsnes ("BGE/BLT are
  exchanged" in Nintendo's book) say `06` branches when S xor V = 0, which is `BGE`; bass and
  WLA DX assemble `bge` to `06`. The upstream p-code branched the other way on both opcodes.
- MAME's disassembler ignores ALT1/ALT2/ALT3/TO/FROM/WITH (`3D 50` prints `ADD R0`, not `ADC R0`);
  it is a per-byte table, so it cannot name the instructions after a prefix.
- bass has no range check on `link #n`: `link #0` assembles to `90` (SBK), `#5` to `95` (SEX),
  `#15` to `97` (ROR), `#16` to `90`. Valid operands are 1 to 4.
- fullsnes says POR bit 3 "forces OBJ mode"; its own table gives bit 4 for OBJ mode and bit 3 for
  freeze-high (the module follows the table).

## Doesn't work

| Gap | Why |
|---|---|
| A prefix (ALT1/2/3, TO/FROM/WITH) in the delay slot of a taken branch should reach the branch *target*; the module applies it to the fall-through address | the prefix state is a decode-time context set for one fixed address; for a branch the target is the other path and SLEIGH cannot set a context at it from inside the slot. A prefix before the branch ("prefix + Bxx + suffix") is handled |
| A multi-byte instruction in a delay slot takes its first byte from the slot and the rest from the target | decoding is by address; real code does not do this |
| Pipeline and bus timing: the ROM read-ahead (GETB after a change of R14/ROMBR sees the old value on the hardware), code cache contents and WAIT states, RAN/RON bus ownership, the MC1 STOP-after-write hang, IRQ and the GO flag as seen by the SNES | hardware state and timing that p-code does not model; the module reads `[ROMBR:R14]` when GETB executes and treats CACHE as setting CBR |
| `SFR`, `SCBR`, `SCMR`, `POR`, `COLR`, `CFGR`... are registers of the GSU side only; the SNES side writes them through memory-mapped ports | the Ghidra memory map has no model of the SNES CPU writing them; set them with `SCBR`/`SCMR` register values or the SNES-side analysis |
| Calls are recognised only in the `LINK #n` + jump form; a jump table in RAM or ROM that `JMP Rn` indexes is not resolved | the target is data-dependent. Both the analyzer and `JMP R11` returns handle the compiler and hand-written idiom |
| The bank of R15 is the instruction's own bank (the address bank is PBR); code run from a bank other than the one it is loaded in is not representable | it is the way Ghidra addresses the image; `LJMP` writes PBR and jumps to the new bank |
| Odd-address word accesses (the hardware swaps the byte pair) are exact in p-code but make the decompiler print `*(a ^ 1)` for every `LDW`/`STW (Rn)` | the address is not known to be even at analysis time. `LMS`/`SMS` and even `LM`/`SM` are plain word accesses |
| The hex prefix `$` instead of `0x` | a Ghidra listing display option |

## Unverified

No SuperFX hardware or emulator was available, and the commercial ROMs (Star Fox, Yoshi's Island...)
were not used, so the following rest on the fullsnes documentation (and its stated "unknown"s)
only: PLOT/RPIX bit-plane addresses and the dither orientation; the carry of FMULT/LMULT (bit 15
of the product) and that LMULT's flags come from the high word; the carry of ALT3 `CMP`/`SBC`
beyond what the documentation's ADD/SUB rows say; LJMP setting CBR to the new offset with the low
four bits cleared; CACHE using the address after the instruction; the "unknown" items fullsnes
lists (RPIX flags, MOVES details); GSU-1/MC1 versus GSU-2 differences.
