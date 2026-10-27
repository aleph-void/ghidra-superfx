// Post-analysis script: disassembles every listed offset that no instruction covers yet (code the
// auto-analysis did not reach: dead code, computed-jump targets...). Used to check the decoding of
// the whole image against the compiler's listing, apart from reachability.
// Script args: <offsets.txt> (one hex address per line, ascending)
//@category Testing

import java.io.BufferedReader;
import java.io.FileReader;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class ForceDis extends GhidraScript {
	@Override
	protected void run() throws Exception {
		int forced = 0;
		try (BufferedReader r = new BufferedReader(new FileReader(getScriptArgs()[0]))) {
			String line;
			while ((line = r.readLine()) != null) {
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				Address a = currentProgram.getAddressFactory().getDefaultAddressSpace()
					.getAddress(Long.parseLong(line, 16));
				if (currentProgram.getListing().getInstructionContaining(a) == null &&
					currentProgram.getListing().getDefinedDataContaining(a) == null) {
					disassemble(a);
					forced++;
				}
			}
		}
		println("forced " + forced + " disassembly starts");
	}
}
