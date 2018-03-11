
#ifndef LLVM_LIB_TARGET_SEMU_SEMU_H
#define LLVM_LIB_TARGET_SEMU_SEMU_H

#include "llvm/Support/TargetRegistry.h"

extern "C" void LLVMInitializeSemuTarget();
extern "C" void LLVMInitializeSemuTargetInfo();
extern "C" void LLVMInitializeSemuTargetMC();

namespace llvm {
	Target& getTheSemuTarget();

	class SemuTargetMachine;
	class SemuSubtarget;
	//class SemuRegisterInfo;
} // end namespace llvm;

#endif

