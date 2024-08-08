# Basic
HLT = 0x00
NOP = 0x01
JMP = 0x03  # goto R1
LDC = 0x04  # R1 -> R2
MRM = 0x05  # R1 -> M[R2]
MMR = 0x06  # M[R1] -> R2
OUT = 0x07  # signal L[R1]
JGT = 0x08  # if R1 .gt 0 jmp R2
OPN = 0x09  # open interrupts
CLS = 0x0A  # close interrupts
LDR = 0x0B  # IP + S1 -> R2
LSP = 0x0C  # R1 -> SP
PSH = 0x0D  # R1 -> [SP++]
POP = 0x0E  # [--SP] -> R1
INT = 0x0F  # INT L[0]
CLL = 0x10  # push IP + 4; push fp; sp -> fp; JMP R1
RET = 0x11  # pop fp; JMP [--SP]
IRX = 0x12  # pop fp; pop h-a; ret; opn
SSP = 0x13  # SP -> R1
MRR = 0x14  # R1 -> R2
LLA = 0x15  # FP + R1 -> R2

# Arithmetic
ADD = 0x21  # R1 +  R2 -> R3
SUB = 0x22  # R1 -  R2 -> R3
MUL = 0x23  # R1 *  R2 -> R3
DIV = 0x24  # R1 // R2 -> R3
MOD = 0x25  # R1 %  R2 -> R3
RSH = 0x26  # R1 >> R2 -> R3
LSH = 0x27  # R1 << R2 -> R3
BOR = 0x28  # R1 | R2 -> R3
XOR = 0x28  # R1 ^ R2 -> R3
BAND = 0x29  # R1 & R2 -> R3

# Emulated
CPT = 0xF0  # U1 -> external breakpoint
AEQ = 0xF1  # if R1 .ne U2 -> exit with EXIT_ASSERT_FAIL
