package superfx;

import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.app.services.AbstractAnalyzer;
import ghidra.app.services.AnalysisPriority;
import ghidra.app.services.AnalyzerType;
import ghidra.app.util.importer.MessageLog;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.lang.Processor;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.FlowOverride;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;
import ghidra.program.model.listing.Program;
import ghidra.program.model.symbol.FlowType;
import ghidra.program.model.symbol.RefType;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.SourceType;
import ghidra.util.exception.CancelledException;
import ghidra.util.task.TaskMonitor;

/**
 * SuperFX control-flow idioms that the SLEIGH p-code cannot express.
 *
 * <ul>
 * <li>Calls. The GSU has no call instruction: {@code LINK #n} puts the address n bytes past
 * itself in R11, and the jump that follows ({@code IWT R15,#addr}, {@code JMP Rn}, with its delay
 * slot) is the call, returning with {@code JMP R11}. When the address LINK computes is the one
 * after that jump and its delay slot, the jump gets a CALL flow override, so the code after it is
 * reached and the decompiler sees a call.</li>
 * <li>Computed jumps. {@code JMP Rn} and {@code LOOP} (target R13) jump to a register that code
 * usually loaded with {@code IWT Rn,#addr} (or {@code MOVE R13,R15}, the loop-start idiom) shortly
 * before. A forward walk tracks those constants (in straight-line code, cleared by anything that
 * writes the register and at unconditional jumps) and gives the jump a reference to the target,
 * which is disassembled; for a call the target also becomes a function.</li>
 * </ul>
 */
public class SuperFXAnalyzer extends AbstractAnalyzer {

	private static final String NAME = "SuperFX Calls and Computed Jumps";
	private static final String DESCRIPTION =
		"Marks LINK + jump pairs as calls and resolves JMP Rn / LOOP targets loaded with IWT.";

	private static final Pattern IWT = Pattern.compile("IWT R(\\d+),#0x([0-9a-fA-F]+)");
	private static final Pattern MOVE = Pattern.compile("MOVE R(\\d+),R(\\d+)");
	private static final Pattern JMP = Pattern.compile("L?JMP R(\\d+)");

	public SuperFXAnalyzer() {
		super(NAME, DESCRIPTION, AnalyzerType.INSTRUCTION_ANALYZER);
		setPriority(AnalysisPriority.CODE_ANALYSIS.after());
		setDefaultEnablement(true);
		setSupportsOneTimeAnalysis();
	}

	@Override
	public boolean canAnalyze(Program program) {
		return program.getLanguage().getProcessor()
			.equals(Processor.findOrPossiblyCreateProcessor("SuperFX"));
	}

	private static boolean isPrefix(Instruction i) {
		String m = i.getMnemonicString();
		return m.equals("ALT1") || m.equals("ALT2") || m.equals("ALT3") || m.equals("TO") ||
			m.equals("FROM") || m.equals("WITH");
	}

	private static boolean isJump(Instruction i) {
		FlowType f = i.getFlowType();
		return f.isJump() && !f.isConditional();
	}

	@Override
	public boolean added(Program program, AddressSetView set, TaskMonitor monitor, MessageLog log)
			throws CancelledException {
		Listing listing = program.getListing();
		AddressSet newCode = new AddressSet();
		AddressSet newFunctions = new AddressSet();

		// 1. LINK #n + jump = call
		for (Instruction link : listing.getInstructions(set, true)) {
			monitor.checkCancelled();
			if (!link.getMnemonicString().equals("LINK")) {
				continue;
			}
			long n = link.getScalar(0).getUnsignedValue();
			Address ret = link.getAddress().add(1 + n);
			Instruction j = link.getNext();
			while (j != null && isPrefix(j)) {
				j = j.getNext();
			}
			// (Shared Return Calls turns a jump to a function entry into CALL_RETURN, a call that
			// does not come back; here it does.)
			if (j == null || j.getFlowOverride() == FlowOverride.CALL ||
				!(isJump(j) || j.getFlowOverride() == FlowOverride.CALL_RETURN)) {
				continue;
			}
			Instruction slot = j.getNext();
			if (slot == null || !j.getAddress().add(j.getLength()).equals(slot.getAddress())) {
				continue;
			}
			Address after = slot.getAddress().add(slot.getLength());
			if (!after.equals(ret)) {
				continue;
			}
			j.setFlowOverride(FlowOverride.CALL);
			newCode.add(ret);
			for (Reference r : j.getReferencesFrom()) {
				if (r.getReferenceType().isFlow() && !r.getReferenceType().isComputed()) {
					newFunctions.add(r.getToAddress());
				}
			}
		}

		// 2. constants loaded into registers, for JMP Rn and LOOP
		Map<Integer, Long> known = new HashMap<>();
		Address prevEnd = null;
		for (Instruction i : listing.getInstructions(set, true)) {
			monitor.checkCancelled();
			if (prevEnd != null && !prevEnd.equals(i.getAddress())) {
				known.clear();
			}
			prevEnd = i.getAddress().add(i.getLength());
			String text = i.toString();
			if (text.startsWith("_")) {
				text = text.substring(1);
			}
			Long target = null;
			boolean call = i.getFlowOverride() == FlowOverride.CALL;
			Matcher m;
			if ((m = JMP.matcher(text)).matches()) {
				int r = Integer.parseInt(m.group(1));
				if (r != 11 && known.containsKey(r)) {
					target = known.get(r);
				}
			}
			else if (text.equals("LOOP") && known.containsKey(13)) {
				target = known.get(13);
			}
			if (target != null) {
				Address to = i.getAddress().getNewAddress(
					(i.getAddress().getOffset() & 0xff0000L) | (target & 0xffff));
				if (program.getMemory().contains(to)) {
					RefType rt = call ? RefType.COMPUTED_CALL
							: text.equals("LOOP") ? RefType.CONDITIONAL_COMPUTED_JUMP
							: RefType.COMPUTED_JUMP;
					boolean have = false;
					for (Reference r : i.getReferencesFrom()) {
						have |= r.getToAddress().equals(to);
					}
					if (!have) {
						i.addMnemonicReference(to, rt, SourceType.ANALYSIS);
					}
					newCode.add(to);
					if (call) {
						newFunctions.add(to);
					}
				}
			}
			// update the tracked constants
			if ((m = IWT.matcher(text)).matches()) {
				known.put(Integer.parseInt(m.group(1)), Long.parseLong(m.group(2), 16));
			}
			else if ((m = MOVE.matcher(text)).matches()) {
				int d = Integer.parseInt(m.group(1)), s = Integer.parseInt(m.group(2));
				if (s == 15) {
					known.put(d, i.getAddress().add(i.getLength()).getOffset() & 0xffff);
				}
				else if (known.containsKey(s)) {
					known.put(d, known.get(s));
				}
				else {
					known.remove(d);
				}
			}
			else if (!isPrefix(i)) {
				for (Object o : i.getResultObjects()) {
					if (o instanceof Register reg && reg.getName().matches("R\\d+")) {
						known.remove(Integer.parseInt(reg.getName().substring(1)));
					}
				}
			}
			FlowType f = i.getFlowType();
			if (f.isTerminal() || (f.isJump() && !f.isConditional() && !call)) {
				// the delay slot is the next instruction; clear after it
				known.clear();
			}
		}

		if (!newCode.isEmpty()) {
			new DisassembleCommand(newCode, null, true).applyTo(program, monitor);
		}
		for (Address a : newFunctions.getAddresses(true)) {
			if (listing.getInstructionAt(a) != null &&
				program.getFunctionManager().getFunctionAt(a) == null) {
				Function f = program.getFunctionManager().getFunctionContaining(a);
				if (f == null || !f.getEntryPoint().equals(a)) {
					new CreateFunctionCmd(a).applyTo(program, monitor);
				}
			}
		}
		return true;
	}
}
