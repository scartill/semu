# Basic
hlt  = 0x00
nop  = 0x01
jmp  = 0x03  # goto R1
ldc  = 0x04  # U1 -> R2
mrm  = 0x05  # R1 -> M[R2]
mmr  = 0x06  # M[R1] -> R2
out  = 0x07  # R1 -> L[R2]
jgt  = 0x08  # if R1 .gt 0 jmp R2
opn  = 0x09  # open interrupts
cls  = 0x0A  # close interrupts
ldr  = 0x0B  # IP + S1 -> R2
lsp  = 0x0C  # R1 -> SP
psh  = 0x0D  # R1 -> [SP++]
pop  = 0x0E  # [SP--] -> R1
int  = 0x0F  # INT R1 -> L[0]
cll  = 0x10  # PSH IP + 4; JMP R1
ret  = 0x11  # JMP [SP--]
irx  = 0x12  # POP h-a; ret; opn
ssp  = 0x13  # SP -> R1

# Arithmetic
add  = 0x20  # R1 + R2 -> R3
sub  = 0x21  # R1 + R2 -> R3

# Emulated
bpt  = 0xF0  # U1 -> external breakpoint 