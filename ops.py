hlt  = 0x00
nop  = 0x01
jmp  = 0x03  # goto R1
add  = 0x04  # R1 + R2 -> R3
ldc  = 0x05  # U1 -> R2
mrm  = 0x06  # R1 -> M[R2]
mmr  = 0x07  # M[R1] -> R2
out  = 0x08  # R1 -> L[R2]
jne  = 0x09  # if R1 ne 0 jmp R2
sub  = 0x0A  # R1 + R2 -> R3
opn  = 0x0B  # open interrupts
cls  = 0x0C  # close interrupts
ldr  = 0x0D  # IP + S1 -> R2
lsp  = 0x0E  # R1 -> SP
psh  = 0x0F  # R1 -> [SP++]
pop  = 0x10  # [SP--] -> R1
int  = 0x11  # INT R1 -> L[0]
cll  = 0x12  # PSH IP + 4; JMP R1
ret  = 0x13  # JMP [SP--]
irx  = 0x14  # POP h-a; ret; opn
bpt  = 0x15  # U1 -> external breakpoint 
ssp  = 0x16  # SP -> R1

intloop  = 0
