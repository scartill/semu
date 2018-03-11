set(LLVM_TARGET_DEFINITIONS Semu.td)

#tablegen(LLVM SemuGenRegisterInfo.inc -gen-register-info)
#tablegen(LLVM SemuGenInstrInfo.inc -gen-instr-info)
#tablegen(LLVM SemuGenAsmWriter.inc -gen-asm-writer)
#tablegen(LLVM SemuGenDAGISel.inc -gen-dag-isel)
#tablegen(LLVM SemuGenCallingConv.inc -gen-callingconv)
tablegen(LLVM SemuGenSubtargetInfo.inc -gen-subtarget)
#tablegen(LLVM SemuGenMCPseudoLowering.inc -gen-pseudo-lowering)
add_public_tablegen_target(SemuCommonTableGen)

add_llvm_target( SemuCodeGen
  SemuTargetInfo.cpp
  SemuTargetMachine.cpp
  SemuSubtarget.cpp
  )

