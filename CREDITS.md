# Credits and provenance

## Upstream

- Project: [ChekeEdd/ghidra-superfx](https://github.com/ChekeEdd/ghidra-superfx), "Ghidra processor
  module (SLEIGH spec) for the Nintendo SuperFX / GSU-1 / GSU-2 co-processor".
- Imported commit: `306d4677ad8d57050c09f507d5df74e38d747ca5` ("Revert Codex auto-review CI; drop
  README section about scripts/review.py", 2026-05-14), SLEIGH spec version 0.3.2.
- License: BSD 3-Clause (`LICENSE`, copyright "2026, ghidra-superfx contributors"). The license and
  the copyright notice are unchanged; Ghidra-Rare's changes are under the same license.
- Authors: the commit author is Edward (`ChekeEdd`); the candidate survey credits `@toxicUnicorn`
  for the module. The README's own references (facts only, no code copied) are bsnes
  (`processor/gsu`, used as a behavioural oracle), SnesLab's Super_FX wiki, the Wikibooks SNES
  Programming Super FX tutorial, jsgroth.dev's SNES coprocessors series and problemkaputt.de's
  fullsnes.

No other SuperFX implementation for Ghidra exists on GitHub (`gh search repos "ghidra superfx"`,
`"superfx sleigh"`, `"ghidra gsu snes"` found none).

## What Ghidra-Rare changed

Everything below is a commit on branch `ghidra-rare` of the fork, on top of the upstream commit.

1. **p-code and prefix model rewritten** (`data/languages/superfx.slaspec`). The upstream spec
   decoded the right mnemonics but its p-code always worked on R0: `TO`/`FROM` copied registers
   directly, `WITH` wrote dummy SREG/DREG registers nobody read, and many operations were wrong.
   Now the ALT1/ALT2/ALT3, TO, FROM and WITH prefixes are tracked at decode time in context fields
   (`alt`, `b`, `sreg`, `dreg`, propagated with `globalset`; Bxx keep them for their delay slot) and
   every ALU, load, store and multiply reads Rs and writes Rd. ALT1/ALT2 on an opcode without such a
   form are ignored and ALT3 falls back to ALT1, as the documentation says; `1n`/`Bn` after `WITH`
   are `MOVE`/`MOVES`. Fixed along the way: carry/overflow of ADD/ADC/SUB/SBC/CMP, `LSR`/`ROL`/
   `ROR`/`ASR`/`DIV2` flags, MERGE flags, MULT/UMULT/FMULT/LMULT (R4 gets the low word), `LOB`/
   `HIB`/`SEX`/`SWAP`, `INC`/`DEC` flags, RAM addressing (`RAMBR`, `$70:0000` window, word access at
   an odd address swaps the byte pair), `LDW`/`STW`/`LDB`/`STB`/`LMS`/`SMS`/`LM`/`SM`/`SBK` (RAM
   address latch), `GETB`/`GETBH`/`GETBL`/`GETBS`/`GETC` through `ROMBR:R14`, `ROMB`/`RAMB`/`CMODE`/
   `COLOR` (with the POR nibble options), `LINK`, `LOOP`, `JMP`/`LJMP`, `CACHE`, `STOP` (a return),
   `JMP R11` (a return).
2. **Branch conditions**: opcode `06` branches when S = V and `07` when S != V (fullsnes: "BGE/BLT
   are exchanged" in Nintendo's book, which MAME and bsnes follow for the names; the upstream p-code
   used the opposite conditions). The listing now says `BGE` for `06`, as the assemblers (bass, WLA
   DX) do.
3. **Delay slots** for every instruction that writes R15 (`IWT R15`, `IBT`, `LMS`, `LM`, `MOVE` with
   R15 as destination; any ALU op with Dreg = R15), not only `IWT R15`. `IWT R15,#imm` is now a
   direct jump (a flow Ghidra's disassembler follows); the other jumps compute the target inside
   the instruction's own bank.
4. **PLOT and RPIX** are p-code (pixel address from SCMR/SCBR/POR, bit planes, dither and
   transparency options) instead of a pseudo-op.
5. **Decompiler start-up fixed**: the pspec and cspec contained XML comments, which Ghidra's
   decompiler cannot parse ("Could not register program"), so the decompiler never worked on this
   language. The comments are removed; the cspec's stack pointer is R10 (R11 is the link register
   and was wrong as a stack pointer).
6. **Analyzer** (`src/main/java/superfx/SuperFXAnalyzer.java`): `LINK #n` followed by a jump whose
   end plus delay slot is the address LINK computes is a call (CALL flow override, the code after it
   is reached, the target becomes a function); `JMP Rn` and `LOOP` get references to targets
   loaded with `IWT Rn,#addr` / `MOVE R13,R15`.
7. **Build and metadata**: `build.gradle`, `extension.properties` (`version=@extversion@`), a
   release zip for Ghidra 12.1.3, 12.1.4 and 12.2; the generated `.sla` is no longer tracked;
   `.ldefs` version 1.0; README brought up to date (see below).
8. **Tests** (`test/`) and the notes in `GHIDRA-RARE.md`.

## Sources used by Ghidra-Rare (facts, not code)

- problemkaputt.de fullsnes "SNES Cart GSU-n" sections (opcode, prefix, flag, bitmap and cache
  documentation).
- bass (byuu, ISC; `architecture snes.gsu`) and WLA DX 10.5 `wla-superfx` (GPL-2.0), both run as
  black-box assemblers; MAME `unidasm -arch superfx` (GPL), run as a black box. No GPL source was
  read for encodings or semantics.
- DiscoC v0.2.0 (GPL-3.0, [DiscoLabOfficial/DiscoC](https://github.com/DiscoLabOfficial/DiscoC))
  SNES demo payloads and the assembly listings its compiler wrote, as real test input (fetched by
  `test/fetch-samples.sh`, never committed).
