
#include "llvm/Support/TargetRegistry.h"
/*
#include "llvm/IR/Attributes.h"
#include "llvm/IR/Function.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/Debug.h"
#include "llvm/Support/raw_ostream.h"

*/

/*
#include "MipsMachineFunction.h"
#include "MipsRegisterInfo.h"
#include "MipsCallLowering.h"
#include "MipsLegalizerInfo.h"
#include "MipsRegisterBankInfo.h"
*/

#include "Semu.h"
#include "SemuTargetMachine.h"
#include "SemuSubtarget.h"

using namespace llvm;

#define DEBUG_TYPE "semu-subtarget"

#define GET_SUBTARGETINFO_TARGET_DESC
#define GET_SUBTARGETINFO_CTOR
#include "SemuGenSubtargetInfo.inc"

void SemuSubtarget::anchor() {}

SemuSubtarget::SemuSubtarget(const Triple &TT, StringRef CPU, StringRef FS,
                             bool little, const SemuTargetMachine &TM,
                             unsigned StackAlignOverride)
    : SemuGenSubtargetInfo(TT, CPU, FS),
      TM(TM), TargetTriple(TT) {

}

