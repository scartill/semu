#include "Semu.h"
#include "llvm/Support/TargetRegistry.h"

using namespace llvm;

Target& llvm::getTheSemuTarget() {
  static Target TheSemuTarget;
  return TheSemuTarget;
}

extern "C" void LLVMInitializeSemuTargetInfo() {
  RegisterTarget<Triple::UnknownArch, /*HasJIT=*/false> X(
	getTheSemuTarget(),
	"Semu", "Slow EMUlator", "Semu");
}

extern "C" void LLVMInitializeSemuTargetMC() {
	// Empty
}
