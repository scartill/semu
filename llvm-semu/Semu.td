//===----------------------------------------------------------------------===//
// Target-independent interfaces which we are implementing
//===----------------------------------------------------------------------===//

include "llvm/Target/Target.td"

//===----------------------------------------------------------------------===//
// Register File, Calling Conv, Instruction Descriptions
//===----------------------------------------------------------------------===//

//include "SemuRegisterInfo.td"
//include "SemuCallingConv.td"
//include "SemuSchedule.td"
//include "SemuInstrInfo.td"

//def SemuInstrInfo : InstrInfo;

//===----------------------------------------------------------------------===//
// Declare the target which we are implementing
//===----------------------------------------------------------------------===//

//def SemuAsmWriter : AsmWriter {
//  string AsmWriterClassName  = "InstPrinter";
//  int Variant = 0;
//}

def Semu : Target {
// Pull in Instruction Info:
//  let InstructionSet = SemuInstrInfo;
//  let AssemblyWriters = [SemuAsmWriter];
   int AllowRegisterRenaming = 1;
}

