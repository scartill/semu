# Basic
hlt  = 0x00
nop  = 0x01
jmp  = 0x03  # goto R1
ldc  = 0x04  # U1 -> R2
mrm  = 0x05  # R1 -> M[R2]
mmr  = 0x06  # M[R1] -> R2
out  = 0x07  # signal L[R1]
jgt  = 0x08  # if R1 .gt 0 jmp R2
opn  = 0x09  # open interrupts
cls  = 0x0A  # close interrupts
ldr  = 0x0B  # IP + S1 -> R2
lsp  = 0x0C  # R1 -> SP
psh  = 0x0D  # R1 -> [SP++]
pop  = 0x0E  # [SP--] -> R1
int  = 0x0F  # INT L[0]
cll  = 0x10  # push IP + 4; push fp; sp -> fp; JMP R1
ret  = 0x11  # pop fp; JMP [SP--]
irx  = 0x12  # pop fp; pop h-a; ret; opn
ssp  = 0x13  # SP -> R1
mrr  = 0x14  # R1 -> R2
lla  = 0x15  # FP + R1 -> R2

# Arithmetic
inv  = 0x20  # ~R1 -> R2
add  = 0x21  # R1 +  R2 -> R3
sub  = 0x22  # R1 -  R2 -> R3
mul  = 0x23  # R1 *  R2 -> R3
div  = 0x24  # R1 // R2 -> R3
mod  = 0x25  # R1 %  R2 -> R3
rsh  = 0x26  # R1 >> R2 -> R3
lsh  = 0x27  # R1 << R2 -> R3
bor  = 0x28  # R1 | R2 -> R3
xor  = 0x28  # R1 ^ R2 -> R3
band = 0x29  # R1 & R2 -> R3

# Emulated
cpt  = 0xF0  # U1 -> external breakpoint
aeq  = 0xF1  # if R1 .ne U2 -> exit with EXIT_ASSERT_FAIL