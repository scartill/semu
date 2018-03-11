
#ifndef LLVM_LIB_TARGET_SEMU_SEMUSUBTARGET_H
#define LLVM_LIB_TARGET_SEMU_SEMUSUBTARGET_H

#include "llvm/CodeGen/TargetSubtargetInfo.h"
/*
#include "MipsFrameLowering.h"
#include "MipsISelLowering.h"
#include "MipsInstrInfo.h"
#include "llvm/CodeGen/SelectionDAGTargetInfo.h"
#include "llvm/CodeGen/GlobalISel/CallLowering.h"
#include "llvm/CodeGen/GlobalISel/LegalizerInfo.h"
#include "llvm/CodeGen/GlobalISel/RegisterBankInfo.h"
#include "llvm/CodeGen/GlobalISel/InstructionSelector.h"
#include "llvm/IR/DataLayout.h"
#include "llvm/MC/MCInstrItineraries.h"
#include "llvm/Support/ErrorHandling.h"
#include <string>
*/

#include "Semu.h"

#define GET_SUBTARGETINFO_HEADER
#include "SemuGenSubtargetInfo.inc"

namespace llvm {

class SemuSubtarget : public SemuGenSubtargetInfo {
  virtual void anchor();

/*
  InstrItineraryData InstrItins;
*/

  const SemuTargetMachine &TM;
  Triple TargetTriple;

/*
  const SelectionDAGTargetInfo TSInfo;
  std::unique_ptr<const MipsInstrInfo> InstrInfo;
  std::unique_ptr<const MipsFrameLowering> FrameLowering;
  std::unique_ptr<const MipsTargetLowering> TLInfo;
*/

public:
	SemuSubtarget(const Triple &TT, StringRef CPU, StringRef FS,
				  bool little, const SemuTargetMachine &TM,
                  unsigned StackAlignOverride);

    void ParseSubtargetFeatures(StringRef CPU, StringRef FS);

  bool isXRaySupported() const override { return false; }
/*
  const SelectionDAGTargetInfo *getSelectionDAGInfo() const override {
    return &TSInfo;
  }

  const MipsInstrInfo *getInstrInfo() const override { 
    return InstrInfo.get(); 
  }
  const TargetFrameLowering *getFrameLowering() const override {
    return FrameLowering.get();
  }
  const MipsRegisterInfo *getRegisterInfo() const override {
    return &InstrInfo->getRegisterInfo();
  }
  const MipsTargetLowering *getTargetLowering() const override {
    return TLInfo.get();
  }
  const InstrItineraryData *getInstrItineraryData() const override {
    return &InstrItins;
  }
*/
protected:
  // GlobalISel related APIs.
/*
  std::unique_ptr<CallLowering> CallLoweringInfo;
  std::unique_ptr<LegalizerInfo> Legalizer;
  std::unique_ptr<RegisterBankInfo> RegBankInfo;
  std::unique_ptr<InstructionSelector> InstSelector;
*/

public:
/*
  const CallLowering *getCallLowering() const override;
  const LegalizerInfo *getLegalizerInfo() const override;
  const RegisterBankInfo *getRegBankInfo() const override;
  const InstructionSelector *getInstructionSelector() const override;
*/
};

} // End llvm namespace

#endif

