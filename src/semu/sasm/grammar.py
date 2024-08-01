# type: ignore
''' Basic grammar '''

import pyparsing as pp

import semu.common.ops as ops
from semu.sasm.fpp import FPP


def g_cmd(literal, op):
    return pp.Literal(literal).setParseAction(lambda _: (FPP.issue_op, op))


id = pp.Word(pp.alphas + '_', pp.alphanums + '_')
comment = pp.Suppress(pp.Literal('//') + pp.SkipTo('\n'))

label = (id + pp.Suppress(':')).setParseAction(lambda r: (FPP.issue_label, r))

reg_indices = {
    'a': 0,
    'b': 1,
    'c': 2,
    'd': 3,
    'e': 4,
    'f': 5,
    'g': 6,
    'h': 7
}

reg_ref = pp.Or([pp.Literal(x) for x in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']])


def g_reg_action(func):
    return pp.And([reg_ref]).setParseAction(lambda r: (func, reg_indices[r[0]]))


reg_op = g_reg_action(FPP.on_reg)


def g_cmd_1(literal, op):
    return g_cmd(literal, op) + reg_op


def g_cmd_2(literal, op):
    return g_cmd(literal, op) + reg_op + reg_op


def g_cmd_3(literal, op):
    return g_cmd(literal, op) + reg_op + reg_op + reg_op


us_dec_const = pp.Regex('[0-9]+').setParseAction(lambda r: (FPP.issue_const, r))
us_const = us_dec_const
s_dec_const = pp.Regex('[+-]?[0-9]+').setParseAction(lambda r: (FPP.issue_sconst, r))
s_const = s_dec_const

refname = pp.Optional(id + pp.Suppress("::")) + id
# Join into [namespace, name] or [name]
refname.setParseAction(lambda r: [r])

ref = (pp.Suppress('&') + refname).setParseAction(lambda r: (FPP.issue_ref, r))

# Basic instructions
hlt_cmd = g_cmd('hlt', ops.HLT)
nop_cmd = g_cmd('nop', ops.NOP)
jmp_cmd = g_cmd_1('jmp', ops.JMP)
ldc_cmd = g_cmd('ldc', ops.LDC) + s_dec_const + reg_op
mrm_cmd = g_cmd_2('mrm', ops.MRM)
mmr_cmd = g_cmd_2('mmr', ops.MMR)
out_cmd = g_cmd_1('out', ops.OUT)
jgt_cmd = g_cmd_2('jgt', ops.JGT)
opn_cmd = g_cmd('opn', ops.OPN)
cls_cmd = g_cmd('cls', ops.CLS)
ldr_cmd = g_cmd('ldr', ops.LDR) + ref + reg_op
lsp_cmd = g_cmd_1('lsp', ops.LSP)
psh_cmd = g_cmd_1('push', ops.PSH)
pop_cmd = g_cmd_1('pop', ops.POP)
int_cmd = g_cmd('int', ops.INT)
cll_cmd = g_cmd_1('cll', ops.CLL)
ret_cmd = g_cmd('ret', ops.RET)
irx_cmd = g_cmd('irx', ops.IRX)
ssp_cmd = g_cmd_1('ssp', ops.SSP)
mrr_cmd = g_cmd_2('mrr', ops.MRR)
lla_cmd = g_cmd('lla', ops.LLA) + us_dec_const + reg_op

# Arithmetic
add_cmd = g_cmd_3('add', ops.ADD)
sub_cmd = g_cmd_3('sub', ops.SUB)
mul_cmd = g_cmd_3('mul', ops.MUL)
div_cmd = g_cmd_3('div', ops.DIV)
mod_cmd = g_cmd_3('mod', ops.MOD)
rsh_cmd = g_cmd_3('rsh', ops.RSH)
lsh_cmd = g_cmd_3('lsh', ops.LSH)
bor_cmd = g_cmd_3('or', ops.BOR)
xor_cmd = g_cmd_3('xor', ops.XOR)
band_cmd = g_cmd_3('and', ops.BAND)

# Emulated
cpt_cmd = g_cmd('.check', ops.CPT) + us_dec_const
aeq_cmd = g_cmd('.assert', ops.AEQ) + reg_op + us_dec_const

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
    ^ cpt_cmd \
    ^ aeq_cmd
