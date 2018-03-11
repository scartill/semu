#ifndef LLVM_LIB_TARGET_SEMU_SEMUTARGETMACHINE_H
#define LLVM_LIB_TARGET_SEMU_SEMUTARGETMACHINE_H

#include <llvm/Target/TargetMachine.h>

#include "Semu.h"
#include "SemuSubtarget.h"

namespace llvm {

class SemuTargetMachine : public LLVMTargetMachine
{
	virtual void anchor();
	SemuSubtarget subtarget;  

public:
	SemuTargetMachine(const Target &T, const Triple &TT, StringRef CPU,
		     StringRef FS, const TargetOptions &Options,
		     Optional<Reloc::Model> RM, Optional<CodeModel::Model> CM,
		     CodeGenOpt::Level OL, bool JIT);

	const SemuSubtarget *getSubtargetImpl(const Function &) const override {
		return &subtarget;
	}

	~SemuTargetMachine() override;
};

}

#endif

