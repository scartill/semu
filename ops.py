
hlt  = 0
nop  = 1
jmp  = 3  # goto R1
add  = 4  # R1 + R2 -> R3
ldc  = 5  # C1 -> R2
mrm  = 6  # R1 -> M[R2]
mmr  = 7  # M[R1] -> R2
out  = 8  # R1 -> L[R2]
jne  = 9  # if R1 ne 0 jmp R2
sub  = 10 # R1 + R2 -> R3
opn  = 11 # open interrupts
cls  = 12 # close interrupts
ldr  = 13 # IP + C1 -> R2
lds  = 14 # R1 -> SP
psh  = 15 # R1 -> [SP++]
pop  = 16 # [SP--] -> R1
int  = 17 # INT R1 -> L[0]


reg0 = 0
reg1 = 1
reg2 = 2
reg3 = 3
reg4 = 4
reg5 = 5
reg6 = 6
reg7 = 7

intloop  = 0
intser   = 1
inttime  = 2
int3     = 3
int4     = 4
int5     = 5
int6     = 6
int7     = 7
int8     = 8
int9     = 9
int10    = 10
int11    = 11
int12    = 12
int13    = 13
int14    = 14
int15    = 15
