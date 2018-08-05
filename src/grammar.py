import pyparsing as pp

import ops
from fpp import FPP

# Grammar
def g_cmd(literal, op):
    return pp.Literal(literal).setParseAction(lambda _: (FPP.issue_op, op))

def g_reg(reg_name, reg_num):
    return pp.Literal(reg_name).setParseAction(lambda _: (FPP.on_reg, reg_num))

id = pp.Word(pp.alphas + "_")
comment = pp.Suppress(pp.Literal("//") + pp.SkipTo("\n"))

label = (id + pp.Suppress(':')).setParseAction(lambda r: (FPP.on_label, r))

reg = pp.Or([
    g_reg('a', 0),
    g_reg('b', 1),
    g_reg('c', 2),
    g_reg('d', 3),
    g_reg('e', 4),
    g_reg('f', 5),
    g_reg('g', 6),
    g_reg('h', 7)
])

def g_cmd_1(literal, op):
    return g_cmd(literal, op) + reg
    
def g_cmd_2(literal, op):
    return g_cmd(literal, op) + reg + reg

def g_cmd_3(literal, op):
    return g_cmd(literal, op) + reg + reg + reg

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
ldc_cmd = g_cmd("ldc", ops.ldc) + us_dec_const + reg
mrm_cmd = g_cmd_2("mrm", ops.mrm)
mmr_cmd = g_cmd_2("mmr", ops.mmr)
out_cmd = g_cmd_1("out", ops.out)
jgt_cmd = g_cmd_2("jgt", ops.jgt)
opn_cmd = g_cmd("opn", ops.opn)
cls_cmd = g_cmd("cls", ops.cls)
ldr_cmd = g_cmd("ldr", ops.ldr) + ref + reg
lsp_cmd = g_cmd_1("lsp", ops.lsp)
psh_cmd = g_cmd_1("push", ops.psh)
pop_cmd = g_cmd_1("pop", ops.pop)
int_cmd = g_cmd("int", ops.int)
cll_cmd = g_cmd_1("cll", ops.cll)
ret_cmd = g_cmd("ret", ops.ret)
irx_cmd = g_cmd("irx", ops.irx)
ssp_cmd = g_cmd_1("ssp", ops.ssp)
mrr_cmd = g_cmd_2("mrr", ops.mrr)
lla_cmd = g_cmd("lla", ops.lla) + us_dec_const + reg

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
aeq_cmd = g_cmd(".assert", ops.aeq) + reg + us_dec_const

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
