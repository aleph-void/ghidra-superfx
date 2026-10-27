// Sequential decode with context propagation: reads cases (hex strings, one per line), places each in
// its own 64-byte slot (zero padded; the slots start at the first block's start), runs the real
// disassembler over the slot (so ALT/TO/WITH/FROM context set by globalset reaches the next
// instruction) and prints, per case, "<hex>|<offset>:<len>:<text>;..." for every instruction that
// starts inside the case bytes. Script args: <cases.txt> <outfile>
//@category Testing

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintStream;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.mem.MemoryBlock;

public class DisSeq extends GhidraScript {
	static final int SLOT = 64;

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		PrintStream out = new PrintStream(args[1]);
		Address base = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(0x8000);
		MemoryBlock blk = currentProgram.getMemory().getBlock(base);
		Listing listing = currentProgram.getListing();
		int idx = 0;
		try (BufferedReader r = new BufferedReader(new FileReader(args[0]))) {
			String line;
			while ((line = r.readLine()) != null) {
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				Address s = base.add((long) idx * SLOT);
				idx++;
				int len = line.length() / 2;
				byte[] b = new byte[SLOT];
				for (int i = 0; i < len; i++) {
					b[i] = (byte) Integer.parseInt(line.substring(2 * i, 2 * i + 2), 16);
				}
				blk.putBytes(s, b);
				AddressSet set = new AddressSet(s, s.add(SLOT - 1));
				DisassembleCommand cmd = new DisassembleCommand(s, set, true);
				cmd.applyTo(currentProgram, monitor);
				StringBuilder sb = new StringBuilder(line).append('|');
				Instruction ins = listing.getInstructionAt(s);
				while (ins != null && ins.getAddress().subtract(s) < len) {
					sb.append(ins.getAddress().subtract(s)).append(':').append(ins.getLength())
						.append(':').append(ins.toString()).append(';');
					ins = ins.getNext();
					if (ins != null && ins.getAddress().compareTo(s.add(SLOT - 1)) > 0) {
						break;
					}
				}
				out.println(sb);
			}
		}
		out.close();
	}
}
