//#include "llvm/CodeGen/Passes.h"
//#include "llvm/CodeGen/TargetPassConfig.h"
//#include "llvm/IR/LegacyPassManager.h"
#include "llvm/Support/TargetRegistry.h"

#include "Semu.h"
#include "SemuTargetMachine.h"

using namespace llvm;

extern "C" void LLVMInitializeSemuTarget() {
  // Register the target machine
  RegisterTargetMachine<SemuTargetMachine> X(getTheSemuTarget());
}

void SemuTargetMachine::anchor() {}

static Reloc::Model getEffectiveRelocModel(Optional<Reloc::Model> RM) {
  if (!RM.hasValue())
    return Reloc::Static;
  return *RM;
}

static CodeModel::Model getEffectiveCodeModel(Optional<CodeModel::Model> CM) {
  if (!CM.hasValue())
    return CodeModel::Small;
  return *CM;
}

SemuTargetMachine::SemuTargetMachine(
    const Target &T,
    const Triple &TT, 
    StringRef CPU, StringRef FS,
    const TargetOptions &Options,
    Optional<Reloc::Model> RM,
    Optional<CodeModel::Model> CM,
    CodeGenOpt::Level OL, bool JIT)
: 
    LLVMTargetMachine(
        T,
        "E-p:32:32-a:32-m:e-n32",
        TT, CPU, FS, Options, 
        getEffectiveRelocModel(RM), 
        getEffectiveCodeModel(CM), OL),

	subtarget(TT, CPU, FS, false, *this, Options.StackAlignmentOverride)
{
}

SemuTargetMachine::~SemuTargetMachine() {
}

