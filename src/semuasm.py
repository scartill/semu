#!/usr/bin/python3

import pyparsing as pp
import sys
import os
import logging as lg
import struct

import ops

# First pass data
class FPD:
    def __init__(self):
        self.cmd_list = list()
        self.offset = 0
        self.label_dict = dict()

    # Handlers
    def issue_word(self, fmt, word):
        bytestr = struct.pack(fmt, word)
        self.cmd_list.append(('bytes', bytestr))
        self.offset += 4

    def issue_usigned(self, word):
        self.issue_word(">I", word)

    def issue_signed(self, word):
        self.issue_word(">i", word)

    def issue_op(self, op):
        lg.debug("Issuing command 0x{0:X}".format(op))
        self.issue_usigned(op)

    def on_label(self, labelname):
        qualified_labelname = self.filename + "." + labelname
        self.label_dict[qualified_labelname] = self.offset
        lg.debug("Label {0} @ {1}".format(qualified_labelname, self.offset))

    def on_reg(self, val):
        self.issue_usigned(val)

    def on_fail(self, r):
        print("Unknown command {0}".format(r))    
        sys.exit(1)
    
    # Macros
    def issue_macro_dw(self, varname):
        self.on_label(varname)
        self.issue_signed(0x00000000)
        
    def issue_macro_call(self, refmatch):
        self.issue_op(ops.ldr)
        self.on_ref(refmatch)    
        self.on_reg(7)               # Using the last for routine address
        self.issue_op(ops.cll)
        self.on_reg(7)
    
    def issue_macro_func(self, labelname):
        self.on_label(labelname)     # Does nothing fancy really
        
    def on_ref(self, match):
        if(len(match) == 1):
            # Unqualified
            labelname = self.filename + "." + match[0]
        else:
            # Qualified
            labelname = match[0] + "." + match[1]
        
        lg.debug("Ref {0}".format(labelname))
        
        current_offset = self.offset
        self.cmd_list.append(('ref', (current_offset, labelname)))
        self.offset += 4 # placeholder-bytes
    
# Grammar
def g_cmd(literal, op):
    return pp.Literal(literal).setParseAction(lambda _: (FPD.issue_op, op))

def g_reg(reg_name, reg_num):
    return pp.Literal(reg_name).setParseAction(lambda _: (FPD.on_reg, reg_num))


comment = pp.Suppress(pp.Literal("//") + pp.SkipTo("\n"))

label = (pp.Word(pp.alphas) + pp.Suppress(':')).setParseAction(lambda r: (FPD.on_label, r[0]))

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

us_dec_const = pp.Regex(
    "[0-9]+").setParseAction(lambda r: (FPD.issue_usigned, int(r[0])))
    
us_const = us_dec_const

s_const = pp.Regex(
    "[\+\-]?[0-9]+").setParseAction(lambda r: (FPD.issue_signed, int(r[0])))
    
refname = pp.Optional(pp.Word(pp.alphas) + pp.Suppress(".")) + pp.Word(pp.alphas)
ref = (pp.Suppress("&") + refname).setParseAction(lambda r: (FPD.on_ref, r))

# Basic instructions
hlt_cmd = g_cmd("hlt", ops.hlt)
nop_cmd = g_cmd("nop", ops.nop)
jmp_cmd = g_cmd_1("jmp", ops.jmp)
ldc_cmd = g_cmd("ldc", ops.ldc) + us_dec_const + reg
mrm_cmd = g_cmd_2("mrm", ops.mrm)
mmr_cmd = g_cmd_2("mmr", ops.mmr)
out_cmd = g_cmd_2("out", ops.out)
jgt_cmd = g_cmd_2("jgt", ops.jgt)
opn_cmd = g_cmd("opn", ops.opn)
cls_cmd = g_cmd("cls", ops.cls)
ldr_cmd = g_cmd("ldr", ops.ldr) + ref + reg
lsp_cmd = g_cmd_1("lsp", ops.lsp)
psh_cmd = g_cmd_1("push", ops.psh)
pop_cmd = g_cmd_1("pop", ops.pop)
int_cmd = g_cmd_1("int", ops.int)
cll_cmd = g_cmd_1("cll", ops.cll)
ret_cmd = g_cmd("ret", ops.ret)
irx_cmd = g_cmd("irx", ops.irx)
ssp_cmd = g_cmd_1("ssp", ops.ssp)

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
bpt_cmd = g_cmd("bpt", ops.bpt) + us_dec_const

# Macros
macro_dw = (pp.Suppress("DW") + refname).setParseAction(lambda r : (FPD.issue_macro_dw, r[0]))
macro_call = (pp.Suppress("CALL") + refname).setParseAction(lambda r : (FPD.issue_macro_call, r))
macro_func = (pp.Suppress("FUNC") + pp.Word(pp.alphas)).setParseAction(lambda r : (FPD.issue_macro_func, r[0]))

# Fail on unknown command
unknown = pp.Regex(".+").setParseAction(lambda r: (FPD.on_fail, r))

cmd = hlt_cmd \
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
    ^ bpt_cmd \
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
    ^ macro_dw \
    ^ macro_call \
    ^ macro_func
    
statement = pp.Optional(label) + pp.Optional(comment) + cmd + pp.Optional(comment)
program = pp.ZeroOrMore(statement ^ comment ^ unknown)

def compile(in_filenames, out_filename):    
    # First pass
    first_pass = FPD()        
    for in_filename in in_filenames:
        lg.info("Processing {0}".format(in_filename))
        sfilename, _ = os.path.splitext(in_filename)
        first_pass.filename = sfilename
        actions = program.parseFile(in_filename)
        for (func, arg) in actions:
            func(first_pass, arg)
    
    # Second pass    
    bytestr = bytearray()
    for (t, d) in first_pass.cmd_list:
        if t == 'bytes':
            bytestr += d
                
        if t == 'ref':
            (ref_offset, labelname) = d
            label_offset = first_pass.label_dict[labelname]
            offset = label_offset - ref_offset
            bytestr += struct.pack(">i", offset)

    # Dumping results
    open(out_filename, "wb").write(bytestr)
   
argc = len(sys.argv)   
if argc < 3:
    print("Usage: semuasm <sources> binary")
    sys.exit(1)

lg.basicConfig(level=lg.DEBUG)
lg.info("SEMU ASM")
compile(sys.argv[1:(argc - 1)], sys.argv[argc - 1])
