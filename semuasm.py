import pyparsing as pp
import sys
import logging as lg
import struct

import ops

# Global first pass results
class FstPassData:
    def __init__(self):
        self.cmd_list = list()
        self.offset = 0
        self.label_dict = dict()

fst_pass = None        

# Handlers
def issue_word(fmt, word):
    global fst_pass
    bytestr = struct.pack(fmt, word)
    fst_pass.cmd_list.append(('bytes', bytestr))
    fst_pass.offset += 4

def issue_usigned(word):
    issue_word(">I", word)    

def issue_signed(word):
    lg.debug("Issuing signed {0}".format(word))
    issue_word(">i", word)

def issue_op(op):
    lg.debug("Issuing command 0x{0:X}".format(op))
    issue_usigned(op)

def on_label(labelname):
    global fst_pass
    lg.debug("New label {0} at {1:X}".format(labelname, fst_pass.offset))
    fst_pass.label_dict[labelname] = fst_pass.offset

def on_reg(val):
    issue_usigned(val)

def on_fail(r):
    print("Unknown command")
    print(r)
    sys.exit(1)
    
# Macros
def issue_macro_dw(varname):
    on_label(varname)
    issue_signed(0x00000000)
    
def issue_macro_call(labelname):
    issue_op(ops.ldr)
    on_ref(labelname)
    on_reg(7)               # Using the last for routine address
    issue_op(ops.cll)
    on_reg(7)
    
def issue_macro_func(labelname):
    on_label(labelname)     # Does nothing fancy really
    
# Grammar
def g_cmd(literal, op):
    return pp.Literal(literal).setParseAction(lambda _: issue_op(op))

def g_reg(reg_name, reg_num):
    return pp.Literal(reg_name).setParseAction(lambda _: on_reg(reg_num))
    
def on_ref(labelname):    
    global fst_pass
    current_offset = fst_pass.offset
    fst_pass.cmd_list.append(('ref', (current_offset, labelname)))
    fst_pass.offset += 4 # placeholder-bytes

comment = pp.Literal("//") + pp.SkipTo("\n")
label = (pp.Word(pp.alphas) + pp.Suppress(':')).setParseAction(lambda r: on_label(r[0]))
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

us_dec_const = pp.Regex(
    "[0-9]+").setParseAction(lambda r: issue_usigned(int(r[0])))
us_const = us_dec_const
s_const = pp.Regex(
    "[\+\-]?[0-9]+").setParseAction(lambda r: issue_signed(int(r[0])))
    
ref = (pp.Suppress("&") + pp.Word(pp.alphas)).setParseAction(lambda r: on_ref(r[0]))
    
hlt_cmd = g_cmd("hlt", ops.hlt)
nop_cmd = g_cmd("nop", ops.nop)
jmp_cmd = g_cmd("jmp", ops.jmp) + reg
add_cmd = g_cmd("add", ops.add) + reg + reg + reg
ldc_cmd = g_cmd("ldc", ops.ldc) + us_dec_const + reg
mrm_cmd = g_cmd("mrm", ops.mrm) + reg + reg
mmr_cmd = g_cmd("mmr", ops.mmr) + reg + reg
out_cmd = g_cmd("out", ops.out) + reg + reg
jne_cmd = g_cmd("jne", ops.jne) + reg + reg
sub_cmd = g_cmd("sub", ops.sub) + reg + reg + reg
opn_cmd = g_cmd("opn", ops.opn)
cls_cmd = g_cmd("cls", ops.cls)
ldr_cmd = g_cmd("ldr", ops.ldr) + ref + reg
lsp_cmd = g_cmd("lsp", ops.lsp) + reg
psh_cmd = g_cmd("psh", ops.psh) + reg
pop_cmd = g_cmd("pop", ops.pop) + reg
int_cmd = g_cmd("int", ops.int) + reg
cll_cmd = g_cmd("cll", ops.cll) + reg
ret_cmd = g_cmd("ret", ops.ret)
irx_cmd = g_cmd("irx", ops.irx)
bpt_cmd = g_cmd("bpt", ops.bpt) + us_dec_const
ssp_cmd = g_cmd("ssp", ops.ssp) + reg

macro_dw = (pp.Suppress("DW") + pp.Word(pp.alphas)).setParseAction(lambda r : issue_macro_dw(r[0]))
macro_call = (pp.Suppress("CALL") + pp.Word(pp.alphas)).setParseAction(lambda r : issue_macro_call(r[0]))
macro_func = (pp.Suppress("FUNC") + pp.Word(pp.alphas)).setParseAction(lambda r : issue_macro_func(r[0]))

unknown = pp.Regex(".+").setParseAction(lambda r: on_fail(r))

cmd = hlt_cmd \
    ^ nop_cmd \
    ^ jmp_cmd \
    ^ add_cmd \
    ^ ldc_cmd \
    ^ mrm_cmd \
    ^ mmr_cmd \
    ^ out_cmd \
    ^ jne_cmd \
    ^ sub_cmd \
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
    ^ macro_dw \
    ^ macro_call \
    ^ macro_func
    
statement = pp.Optional(label) + pp.Optional(comment) + cmd + pp.Optional(comment)
program = pp.ZeroOrMore(statement ^ comment ^ unknown)

def compile(in_filename, out_filename):
    global fst_pass

    fst_pass = FstPassData()
    program.parseFile(in_filename)
    bytestr = bytearray()

    for (t, d) in fst_pass.cmd_list:
        if t == 'bytes':
            bytestr += d
                
        if t == 'ref':
            (ref_offset, labelname) = d
            label_offset = fst_pass.label_dict[labelname]
            offset = label_offset - ref_offset
            bytestr += struct.pack(">i", offset)
            lg.debug("Issuing offset {0} of reference to {1}".format(offset, labelname))

    open(out_filename, "wb").write(bytestr)
    
if len(sys.argv) != 3:
    print("Usage: semuasm source.sasm binary")
    sys.exit(1)

lg.basicConfig(level=lg.DEBUG)
lg.info("SEMU ASM")
compile(sys.argv[1], sys.argv[2])
