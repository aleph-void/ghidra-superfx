# ghidra-superfx

A [Ghidra](https://github.com/NationalSecurityAgency/ghidra) processor
module (SLEIGH spec) for Nintendo's **SuperFX / GSU-1 / GSU-2 / MARIO Chip**
co-processor, the 16-bit RISC found inside enhancement-chip SNES cartridges.

| Field | Value |
|---|---|
| Language id | `SuperFX:LE:24:default` |
| Tested against | Ghidra 12.1.3, 12.1.4 and 12.2 (Ghidra-Rare release zips, one per version; see [GHIDRA-RARE.md](GHIDRA-RARE.md)) |
| Version check | The release zips carry the Ghidra version they were built for in `extension.properties` (`version=@extversion@` is filled in by the build); build your own with `gradle buildExtension` for another version |
| Verified | Decode against bass and WLA DX (two assemblers) and MAME `unidasm`, 106 hand-computed emulator cases, and the GSU code the DiscoC compiler writes; the numbers are in [GHIDRA-RARE.md](GHIDRA-RARE.md). (Upstream's own check: Star Fox (USA) Rev 2, SHA1 `cf08148cd8f26d51f8c67c956179dfc594e7a4f1`, against bsnes; that ROM is not part of this repository's tests) |
| License | BSD 3-Clause |

## Supported games

The SuperFX co-processor was used by:

- Star Fox (USA / EU / JP, all revisions)
- Star Fox 2 (released 2017 via SNES Classic; also playable from leaked
  prototype ROMs)
- Yoshi's Island (a.k.a. Super Mario World 2)
- Stunt Race FX (a.k.a. Wild Trax)
- Doom (SNES)
- Vortex (a.k.a. Citadel)
- Dirt Trax FX
- Winter Gold

Any GSU code in these cartridges decodes through this module.

## Install

### Option A — drop-in folder (fastest)

1. Download or `git clone` this repo.
2. Copy the entire repo contents into a folder named `ghidra-superfx`
   under your Ghidra user extensions directory:
   - Windows: `%APPDATA%\ghidra\ghidra_<VERSION>_PUBLIC\Extensions\ghidra-superfx\`
   - Linux: `~/.config/ghidra/ghidra_<VERSION>_PUBLIC/Extensions/ghidra-superfx/`
   - macOS: `~/Library/ghidra/ghidra_<VERSION>_PUBLIC/Extensions/ghidra-superfx/`
3. (Re)start Ghidra. The module loads automatically; no further GUI
   configuration is required.
4. When importing a ROM, choose `SuperFX:LE:24:default` as the
   Language / Compiler.

### Option B — release zip (for File → Install Extensions)

Prebuilt zips for Ghidra 12.1.3, 12.1.4 and 12.2 are on the fork's Releases page:

1. Ghidra → File → Install Extensions… → `+` → pick the downloaded
   `ghidra-superfx-vX.Y.Z.zip`.
2. Tick the new "SuperFX" entry, click OK, restart Ghidra.
3. Same Language selection step as Option A.

## What the module does

- Decodes all ~80 GSU instructions (STOP / NOP / CACHE / LSR / ROL,
  10 conditional branches, register-encoded ALU (ADD / SUB / AND / OR /
  XOR / MULT / UMULT / INC / DEC), TO / WITH / FROM register
  prefixes, LOAD / STORE word & byte families, IBT / IWT / LMS / SMS /
  LM / SM immediate-and-memory transfers, JMP / LJMP, LINK, LOOP,
  PLOT / RPIX / COLOR / CMODE / MERGE graphics ops, FMULT / LMULT
  fractional multiplies, GETB / GETC ROM-byte fetches, RAMB / ROMB
  bank-register writes, HIB / LOB / SEX / ROR / ASR / DIV2 / SWAP /
  NOT bit ops).
- Models the **ALT1 / ALT2 / ALT3 and TO / FROM / WITH prefix state** through SLEIGH
  context fields propagated with `globalset(inst_next, …)`: every ALU, load, store and
  multiply reads the selected source register (Sreg) and writes the selected destination
  register (Dreg); ALT prefixes that do not apply to an opcode are ignored (ALT3 acts as
  ALT1), and `1n`/`Bn` after `WITH` are `MOVE`/`MOVES`.
- Models the **branch delay slot** on every taken control-flow
  instruction (BRA + 10 conditional branches, JMP, LJMP, LOOP, and any write to
  R15) via SLEIGH's `delayslot(1)` directive — important
  for accurate P-code / decompiler output.
- Models **PLOT / RPIX** (bit-plane pixel writes and reads from SCMR/SCBR/POR) and the
  POR nibble options of COLOR/GETC in p-code.
- An analyzer marks `LINK #n` + jump as a call and resolves `JMP Rn` / `LOOP` targets
  loaded with `IWT`.
- Maps the special-function registers `SFR`, `PBR`, `ROMBR`, `RAMBR`,
  `CBR`, `SCBR`, `SCMR`, `COLR`, `POR`, `BRAMR`, `CFGR` plus the
  individual SFR flag bits as discrete varnodes.

See [`CHANGELOG.md`](CHANGELOG.md) for the version-by-version history
and the slaspec header for full design rationale.

## Limitations / known corner cases

Status of the limitations upstream listed (Ghidra-Rare, see [GHIDRA-RARE.md](GHIDRA-RARE.md) for the rest):

- **Fixed:** "`SREG` / `DREG` selectors only partially modelled" (CHANGELOG, "scheduled for
  v0.4"): `TO`/`FROM`/`WITH` now drive the registers every following operation reads and writes.
- **Fixed:** branches to and calls of other code were not followed (no p-code consequence of
  `LINK`, no references for `JMP Rn`/`LOOP`): the bundled analyzer handles them.
- **Remaining, display only:** Hex prefix style (`$` vs `0x`) is a Ghidra-wide Listing display
  option (Edit → Tool Options → Listing Display). This module emits
  the default `0x` prefix; the user-facing choice is not slaspec
  controllable. (Confirmed by surveying Ghidra-shipped 6502, 65C02,
  CR16C specs and the SLEIGH `tokens` documentation.)
- **Remaining:** an `ALT1` / `ALT2` / `ALT3` (or `TO`/`FROM`/`WITH`) prefix appearing **inside the
  delay slot of a taken branch** marks, on the hardware, the instruction at the branch *target*.
  The prefix state is a decode-time context set for the byte after the prefix, so the module
  applies it to the physical fall-through address, which is right in straight-line code and when
  the prefix is placed before the branch ("prefix + Bxx + suffix": that works), but not for this
  corner case. A taken-vs-not-taken branch cannot give the target a context from inside the slot
  in SLEIGH without making the slot part of the branch instruction.
- **Remaining:** a multi-byte instruction in a delay slot executes its first byte from the slot and
  the rest from the branch target (fullsnes); the module decodes it as one instruction at the slot
  address.

## Validation methodology

The module is byte-validated against bsnes' SuperFX disassembler
(`bsnes/processor/gsu/disassembler.cpp` in bsnes-emu/bsnes, GPLv3+),
used purely as a behavioral oracle — its text output is compared
against this module's, and no bsnes source code is incorporated into
the SLEIGH spec or any artifact shipped from this repo. The
validation harness itself lives in the parent Star Fox decomp
project (private repository, not yet published) and is not
redistributed here. It extracts a chunk of GSU code from
a real Star Fox ROM, walks it linearly through both decoders, then
diffs the two text outputs line by line. Across 64 KB of real GSU
code (covering all 12 RPC entry points in Star Fox, plus their
helpers and the AC1D per-frame driver) the two decoders agree on
100 % of byte boundaries and 100 % of mnemonic families.

## References

This module was developed without copying source code from any
GPL-licensed emulator and without consulting any leaked source
material. The references below were used only for facts —
instruction encodings, hardware behaviour, mnemonic conventions,
and SLEIGH language idioms — i.e., to verify *what* a given
instruction does, not *how* an existing implementation expresses
it. Facts are not copyrightable; nothing beyond facts was carried
across.

- bsnes-emu/bsnes `processor/gsu/` (GPLv3+) — behavioral reference
  for instruction encoding, mnemonic naming, and ALT-state tables.
  Used as a black-box oracle (run the binary, compare text output);
  no bsnes source code is incorporated into this repo.
- bsnes-jg fork (GPLv3+) — same usage; consulted for the STOP
  pipeline behaviour cited in `superfx.slaspec`.
- SnesLab Super_FX wiki — register layout & SFR bit definitions.
- Wikibooks SNES Programming Super FX tutorial — opcode summary.
- jsgroth.dev SNES coprocessors part 7 — pipeline, cache, and
  delay-slot documentation.
- problemkaputt.de fullsnes.htm — SNES bus integration.
- Ghidra's MIPS / 6502 / ARM SLEIGH specs (Apache-2.0) — SLEIGH
  idiom reference (`delayslot`, `globalset`, context register
  patterns). Methods/patterns only; no constructor text or other
  expressive content was copied. Apache-2.0 attribution is
  therefore not legally required for this repo, but the
  acknowledgement is recorded here in good faith.

## Origin

Originally developed as Phase 1a of a clean-room Star Fox SNES
decompilation effort (private repository, not yet published).
Split out into a standalone repo so it is useful to anyone
reverse-engineering a SuperFX game, not only Star Fox.

## Contributing

Bug reports and PRs are welcome. If you find a real ROM where this
module's disassembly disagrees with bsnes ground truth, please open
an issue with the ROM SHA1, the GSU PC address, and the byte sequence
that misdecodes.

## License

BSD 3-Clause — see [`LICENSE`](LICENSE).
