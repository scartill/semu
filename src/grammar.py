import pyparsing as pp

import ops
from fpp import FPP

# Grammar

def g_cmd(literal, op):
    return pp.Literal(literal).setParseAction(lambda _: (FPP.issue_op, op))

id = pp.Word(pp.alphas + "_")
comment = pp.Suppress(pp.Literal("//") + pp.SkipTo("\n"))

label = (id + pp.Suppress(':')).setParseAction(lambda r: (FPP.on_label, r))

reg_indices = {
    'a' : 0,
    'b' : 1,
    'c' : 2,
    'd' : 3,
    'e' : 4,
    'f' : 5,
    'g' : 6,
    'h' : 7
}

reg_ref = pp.Or([pp.Literal(x) for x in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']])

def g_reg_action(func):
    return reg_ref.setParseAction(lambda r: (func, reg_indices[r[0]]))

reg_op = g_reg_action(FPP.on_reg)

def g_cmd_1(literal, op):
    return g_cmd(literal, op) + reg_op
    
def g_cmd_2(literal, op):
    return g_cmd(literal, op) + reg_op + reg_op

def g_cmd_3(literal, op):
    return g_cmd(literal, op) + reg_op + reg_op + reg_op

us_dec_const = pp.Regex("[0-9]+").setParseAction(lambda r: (FPP.on_uconst, r))    
us_const = us_dec_const
s_const = pp.Regex("[\+\-]?[0-9]+").setParseAction(lambda r: (FPP.on_sconst, r))
    
refname = pp.Optional(id + pp.Suppress("::")) + id
refname.setParseAction(lambda r: [r[:]])  # Join tokens
ref = (pp.Suppress("&") + refname).setParseAction(lambda r: (FPP.on_ref, r))

# Basic instructions
hlt_cmd = g_cmd("hlt", ops.hlt)
nop_cmd = g_cmd("nop", ops.nop)
jmp_cmd = g_cmd_1("jmp", ops.jmp)
ldc_cmd = g_cmd("ldc", ops.ldc) + us_dec_const + reg_op
mrm_cmd = g_cmd_2("mrm", ops.mrm)
mmr_cmd = g_cmd_2("mmr", ops.mmr)
out_cmd = g_cmd_1("out", ops.out)
jgt_cmd = g_cmd_2("jgt", ops.jgt)
opn_cmd = g_cmd("opn", ops.opn)
cls_cmd = g_cmd("cls", ops.cls)
ldr_cmd = g_cmd("ldr", ops.ldr) + ref + reg_op
lsp_cmd = g_cmd_1("lsp", ops.lsp)
psh_cmd = g_cmd_1("push", ops.psh)
pop_cmd = g_cmd_1("pop", ops.pop)
int_cmd = g_cmd("int", ops.int)
cll_cmd = g_cmd_1("cll", ops.cll)
ret_cmd = g_cmd("ret", ops.ret)
irx_cmd = g_cmd("irx", ops.irx)
ssp_cmd = g_cmd_1("ssp", ops.ssp)
mrr_cmd = g_cmd_2("mrr", ops.mrr)
lla_cmd = g_cmd("lla", ops.lla) + us_dec_const + reg_op

# Arithmetic
inv_cmd = g_cmd_2("inv", ops.inv)
add_cmd = g_cmd_3("add", ops.add)
sub_cmd = g_cmd_3("sub", ops.sub)
mul_cmd = g_cmd_3("mul", ops.mul)
div_cmd = g_cmd_3("div", ops.div)
mod_cmd = g_cmd_3("mod", ops.mod)
rsh_cmd = g_cmd_3("rsh", ops.rsh)
lsh_cmd = g_cmd_3("lsh", ops.lsh)
bor_cmd = g_cmd_3("or", ops.bor)
xor_cmd = g_cmd_3("xor", ops.xor)
band_cmd = g_cmd_3("and", ops.band)

# Emulated
bpt_cmd = g_cmd(".break", ops.bpt) + us_dec_const
aeq_cmd = g_cmd(".assert", ops.aeq) + reg_op + us_dec_const

asm_cmd = hlt_cmd \
    ^ nop_cmd \
    ^ jmp_cmd \
    ^ ldc_cmd \
    ^ mrm_cmd \
    ^ mmr_cmd \
    ^ out_cmd \
    ^ jgt_cmd \
    ^ opn_cmd \
    ^ cls_cmd \
    ^ ldr_cmd \
    ^ lsp_cmd \
    ^ psh_cmd \
    ^ pop_cmd \
    ^ int_cmd \
    ^ cll_cmd \
    ^ ret_cmd \
    ^ irx_cmd \
    ^ ssp_cmd \
    ^ inv_cmd \
    ^ add_cmd \
    ^ sub_cmd \
    ^ mul_cmd \
    ^ div_cmd \
    ^ mod_cmd \
    ^ rsh_cmd \
    ^ lsh_cmd \
    ^ bor_cmd \
    ^ xor_cmd \
    ^ band_cmd \
    ^ mrr_cmd \
    ^ lla_cmd \
    ^ bpt_cmd \
    ^ aeq_cmd
