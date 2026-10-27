// P-code semantics check for the SuperFX module. Reads test/emu/cases.txt (expectations worked out by
// hand from the fullsnes GSU documentation), and for each case writes the code at 0x1000,
// sets registers and memory, emulates with Ghidra's EmulatorHelper until the PC reaches the end of
// the code (or the address given by "until"), and compares registers, flags and memory.
//
// Case format (one directive per line, '#' comments):
//   case <name> [only st70|st72] [broken]   "broken" cases carry a deliberately wrong expectation
//   code <hex>                              bytes placed at 0x1000
//   until <hex-address>                     stop when PC reaches this address (default: end of code)
//   set <reg> <value> | set mem:<hex-addr> <value>
//   expect <reg> <value> | expect mem:<hex-addr> <value>
//   end
// Script args: <cases.txt> <outfile>
//@category Testing

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;

public class EmuTest extends GhidraScript {

	private static class Case {
		String name;
		String only = "";
		boolean broken;
		byte[] code;
		List<long[]> extra = new ArrayList<>();   // {address} paired with extraCode
		List<byte[]> extraCode = new ArrayList<>();
		long until = -1;
		Map<String, Long> set = new LinkedHashMap<>();
		Map<String, Long> expect = new LinkedHashMap<>();
	}

	private List<Case> load(String path) throws Exception {
		List<Case> cases = new ArrayList<>();
		Case c = null;
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				int h = line.indexOf('#');
				if (h >= 0) {
					line = line.substring(0, h);
				}
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				String[] f = line.split("\\s+");
				switch (f[0]) {
					case "case":
						c = new Case();
						c.name = f[1];
						for (int i = 2; i < f.length; i++) {
							if (f[i].equals("only")) {
								c.only = f[++i];
							}
							else if (f[i].equals("broken")) {
								c.broken = true;
							}
						}
						break;
					case "code":
						String hex = String.join("", java.util.Arrays.copyOfRange(f, 1, f.length));
						c.code = new byte[hex.length() / 2];
						for (int i = 0; i < c.code.length; i++) {
							c.code[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
						}
						break;
					case "codeat": {
						String h2 = String.join("", java.util.Arrays.copyOfRange(f, 2, f.length));
						byte[] bb = new byte[h2.length() / 2];
						for (int i = 0; i < bb.length; i++) {
							bb[i] = (byte) Integer.parseInt(h2.substring(2 * i, 2 * i + 2), 16);
						}
						c.extra.add(new long[] { Long.parseLong(f[1], 16) });
						c.extraCode.add(bb);
						break;
					}
					case "until":
						c.until = Long.parseLong(f[1], 16);
						break;
					case "set":
						c.set.put(f[1], Long.decode(f[2]));
						break;
					case "expect":
						c.expect.put(f[1], Long.decode(f[2]));
						break;
					case "end":
						cases.add(c);
						break;
					default:
						throw new IllegalArgumentException("bad line: " + line);
				}
			}
		}
		return cases;
	}

	private Address addr(long off) {
		return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(off);
	}

	private void ensureBlocks() throws Exception {
		ghidra.program.model.mem.Memory mem = currentProgram.getMemory();
		for (long[] r : new long[][] { { 0x018000, 0x1000 }, { 0x700000, 0x2000 }, { 0x710000, 0x100 } }) {
			if (mem.getBlock(addr(r[0])) == null) {
				mem.createInitializedBlock("blk" + Long.toHexString(r[0]), addr(r[0]), r[1], (byte) 0,
					monitor, false);
			}
		}
	}

	private long readMem(EmulatorHelper emu, String key) {
		boolean w = key.startsWith("mem16:");
		long a = Long.parseLong(key.substring(w ? 6 : 4), 16);
		byte[] bb = emu.readMemory(addr(a), w ? 2 : 1);
		return w ? ((bb[0] & 0xffL) | ((bb[1] & 0xffL) << 8)) : (bb[0] & 0xff);
	}

	private String runCase(Case c) throws Exception {
		Address start = addr(0x8000);
		Address end = c.until >= 0 ? addr(c.until) : start.add(c.code.length);
		clearListing(new AddressSet(addr(0x8000), addr(0x80ff)));
		clearListing(new AddressSet(addr(0x018000), addr(0x018fff)));
		setBytes(addr(0x8000), new byte[256]);
		setBytes(addr(0x018000), new byte[4096]);
		setBytes(addr(0x700000), new byte[8192]);
		setBytes(addr(0x710000), new byte[256]);
		setBytes(start, c.code);
		disassemble(start);
		for (int i = 0; i < c.extra.size(); i++) {
			setBytes(addr(c.extra.get(i)[0]), c.extraCode.get(i));
			disassemble(addr(c.extra.get(i)[0]));
		}
		EmulatorHelper emu = new EmulatorHelper(currentProgram);
		try {
			for (Map.Entry<String, Long> e : c.set.entrySet()) {
				if (e.getKey().startsWith("mem16:")) {
					long v = e.getValue();
					emu.writeMemory(addr(Long.parseLong(e.getKey().substring(6), 16)),
						new byte[] { (byte) v, (byte) (v >> 8) });
				}
				else if (e.getKey().startsWith("mem:")) {
					emu.writeMemory(addr(Long.parseLong(e.getKey().substring(4), 16)),
						new byte[] { (byte) (long) e.getValue() });
				}
				else {
					emu.writeRegister(e.getKey(), e.getValue());
				}
			}
			emu.writeRegister(emu.getPCRegister(), start.getOffset());
			int steps = 0;
			while (!emu.getExecutionAddress().equals(end)) {
				if (++steps > 400) {
					return "did not reach the end (pc " + emu.getExecutionAddress() + ")";
				}
				if (!emu.step(monitor)) {
					return "emulation error at " + emu.getExecutionAddress() + ": " +
						emu.getLastError();
				}
			}
			StringBuilder bad = new StringBuilder();
			for (Map.Entry<String, Long> e : c.expect.entrySet()) {
				long got;
				if (e.getKey().startsWith("mem")) {
					got = readMem(emu, e.getKey());
				}
				else if (e.getKey().equals("PC")) {
					got = emu.getExecutionAddress().getOffset();
				}
				else {
					got = emu.readRegister(e.getKey()).longValue();
				}
				if (got != e.getValue()) {
					bad.append(String.format(" %s=0x%x (expected 0x%x)", e.getKey(), got,
						e.getValue()));
				}
			}
			return bad.length() == 0 ? null : bad.toString().trim();
		}
		finally {
			emu.dispose();
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		List<Case> cases = load(args[0]);
		PrintStream out = new PrintStream(args[1]);
		ensureBlocks();
		String lang = currentProgram.getLanguageID().getIdAsString();
		String variant = "sfx";
		int pass = 0, fail = 0, brokenSeen = 0, brokenMissed = 0;
		for (Case c : cases) {
			if (!c.only.isEmpty() && !c.only.equals(variant)) {
				continue;
			}
			String err = runCase(c);
			if (c.broken) {
				if (err != null) {
					brokenSeen++;
					out.println("PASS (broken expectation detected) " + c.name + ": " + err);
				}
				else {
					brokenMissed++;
					out.println("FAIL " + c.name + ": the deliberately wrong expectation passed");
				}
			}
			else if (err == null) {
				pass++;
				out.println("PASS " + c.name);
			}
			else {
				fail++;
				out.println("FAIL " + c.name + ": " + err);
			}
		}
		out.printf("emulation (%s): %d passed, %d failed, broken expectation %s%n", lang, pass,
			fail + brokenMissed, brokenSeen > 0 && brokenMissed == 0 ? "detected" : "NOT detected");
		out.close();
	}
}
