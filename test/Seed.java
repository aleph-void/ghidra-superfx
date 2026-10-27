// Pre-analysis script: disassembles and creates a function at every address listed in the file
// (one hex address per line). Script args: <seeds.txt>
//@category Testing

import java.io.BufferedReader;
import java.io.FileReader;

import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;

public class Seed extends GhidraScript {
	@Override
	protected void run() throws Exception {
		try (BufferedReader r = new BufferedReader(new FileReader(getScriptArgs()[0]))) {
			String line;
			while ((line = r.readLine()) != null) {
				line = line.trim();
				if (line.isEmpty()) {
					continue;
				}
				Address a = currentProgram.getAddressFactory().getDefaultAddressSpace()
					.getAddress(Long.parseLong(line, 16));
				disassemble(a);
				createFunction(a, null);
			}
		}
	}
}
