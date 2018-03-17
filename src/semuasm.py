#!/usr/bin/python3

import pyparsing as pp
import sys
import os
import logging as lg
import struct

import ops

# Struct definition
class Struct:
    def __init__(self, name):
        self.name = name
        self.fields = dict()
        self.size = 0                       # size in 4-byte words
        
    def add_field(self, name, width):
        lg.debug("Field {0}:{1}:{2}".format(name, width, self.size))
        self.fields[name] = self.size
        self.size += width
        
    def get_offset(self, fieldname):
        return self.fields[fieldname] * 4   # offset in bytes

# First pass data
class FPD:
    def __init__(self):      
        self.cmd_list = list()
        self.offset = 0
        self.namespace = "<global>"
        self.label_dict = dict()
        self.context = None
        self.structs = dict()
        
    def get_qualified_name(self, name, namespace = None):    
        if(namespace == None):
            namespace = self.namespace    
        return namespace + "::" + name

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
        
    def on_uconst(self, tokens):
        word = int(tokens[0])
        self.issue_usigned(word)
        
    def on_sconst(self, tokens):
        word = int(tokens[0])
        self.issue_signed(word)        

    def on_label(self, tokens):
        labelname = tokens[0]
        qlabelname = self.get_qualified_name(labelname)
        self.label_dict[qlabelname] = self.offset
        lg.debug("Label {0} @ {1}".format(qlabelname, self.offset))

    def on_reg(self, val):
        self.issue_usigned(val)
    
    def on_ref(self, tokens):
        if(len(tokens) == 1):
            # Unqualified
            labelname = self.get_qualified_name(tokens[0])
        else:
            # Qualified
            labelname = self.get_qualified_name(tokens[1], tokens[0]) # name, namespace
        
        lg.debug("Ref {0}".format(labelname))
        
        current_offset = self.offset
        self.cmd_list.append(('ref', (current_offset, labelname)))
        self.offset += 4 # placeholder-bytes        

    def on_fail(self, r):
        raise Exception("Unknown command {0}".format(r))
    
    # Macros
    def issue_macro_dw(self, tokens):
        self.on_label(tokens)
        self.issue_usigned(0x00000000)
        
    def issue_macro_call(self, tokens):
        self.issue_op(ops.ldr)
        self.on_ref(tokens)
        self.on_reg(7)               # Using the last for routine address
        self.issue_op(ops.cll)
        self.on_reg(7)
    
    def issue_macro_func(self, tokens):
        self.on_label(tokens)        # Does nothing fancy really
        
    def macro_begin_struct(self, tokens):
    
        name = tokens[0]
        qname = self.get_qualified_name(name)
        
        if(self.context != None):
            raise Exception("Bad context")
        self.context = Struct(qname)
        
    def macro_struct_field(self, tokens):
        type = tokens[0]
        fname = tokens[1]
        
        if(type == "DW"):
            width = 1
        else:
            raise Exception("Bad type {0}".format(type))
        
        s = self.context
        if(self.context == None):
            raise Exception("Bad context")
            
        s.add_field(fname, width)        
        
    def macro_struct_end(self, tokens):    
        s = self.context
        if(self.context == None):
            raise Exception("Bad context")
            
        self.structs[s.name] = s
        self.context = None
        lg.debug("Struct {0}".format(s.name))
        
    def issue_macro_ds(self, tokens):
        if(len(tokens) == 3):
            namespace = tokens[0]
            sname = tokens[1]
            name = tokens[2]
        else:
            namespace = None
            sname = tokens[0]
            name = tokens[1]
            
        qsname = self.get_qualified_name(sname, namespace)
        s = self.structs[qsname]
        words = s.size
        self.on_label([name])
        # Issue placeholder-bytes
        for _ in range(words):
            self.issue_usigned(0x00000000)
    
    def issue_macro_fptr_head(self, tokens):
        self.issue_op(ops.ldr)
        
    def issue_macro_rptr_head(self, tokens):
        self.issue_op(ops.mmr) 
    
    def issue_macro_ptr_tail(self, tokens):
        # before: command to to load struct address to reg
        # for FPTR: ldr &ref
        # for RPTR: mrm source-reg
        if(len(tokens) == 3):
            fname = tokens[0]
            namespace = tokens[1]
            sname = tokens[2]
        else:
            fname = tokens[0]
            namespace = None
            sname = tokens[1]
            
        qsname = self.get_qualified_name(sname, namespace)
        s = self.structs[qsname]
        offset = s.get_offset(fname)        
            
        self.on_reg(7)               # Using the last ('h') for struct address
        self.issue_op(ops.ldc)       # Loading the offset
        self.issue_usigned(offset)
        self.on_reg(6)               # Using 'g' for field offset
        self.issue_op(ops.add)       # Adding the offset
        self.on_reg(7)
        self.on_reg(6)
        # after: target reg
    
# Grammar
def g_cmd(literal, op):
    return pp.Literal(literal).setParseAction(lambda _: (FPD.issue_op, op))

def g_reg(reg_name, reg_num):
    return pp.Literal(reg_name).setParseAction(lambda _: (FPD.on_reg, reg_num))


comment = pp.Suppress(pp.Literal("//") + pp.SkipTo("\n"))

label = (pp.Word(pp.alphas) + pp.Suppress(':')).setParseAction(lambda r: (FPD.on_label, r))

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

us_dec_const = pp.Regex("[0-9]+").setParseAction(lambda r: (FPD.on_uconst, r))    
us_const = us_dec_const
s_const = pp.Regex("[\+\-]?[0-9]+").setParseAction(lambda r: (FPD.on_sconst, r))
    
refname = pp.Optional(pp.Word(pp.alphas) + pp.Suppress("::")) + pp.Word(pp.alphas)
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
macro_dw = (pp.Suppress("DW") + refname).setParseAction(lambda r: (FPD.issue_macro_dw, r))
macro_call = (pp.Suppress("CALL") + refname).setParseAction(lambda r: (FPD.issue_macro_call, r))
macro_func = (pp.Suppress("FUNC") + pp.Word(pp.alphas)).setParseAction(lambda r: (FPD.issue_macro_func, r))

# Macro-struct
struct_begin = (pp.Suppress("STRUCT") + pp.Word(pp.alphas)).setParseAction(lambda r: (FPD.macro_begin_struct, r))
field_type = pp.Or(pp.Literal("DW"))
struct_field = (field_type + pp.Word(pp.alphas)).setParseAction(lambda r: (FPD.macro_struct_field, r))
struct_end = pp.Suppress("END").setParseAction(lambda r: (FPD.macro_struct_end, r))
macro_struct = struct_begin + pp.OneOrMore(struct_field) + struct_end

macro_ds = (pp.Suppress("DS") + refname + pp.Word(pp.alphas)).setParseAction(lambda r: (FPD.issue_macro_ds, r))

ptr_tail = (pp.Word(pp.alphas) + pp.Suppress("#") + refname).setParseAction(lambda r: (FPD.issue_macro_ptr_tail, r))
fptr_head = pp.Literal("FPTR").setParseAction(lambda r: (FPD.issue_macro_fptr_head, r))
rptr_head = pp.Literal("RPTR").setParseAction(lambda r: (FPD.issue_macro_rptr_head, r))
macro_fptr = fptr_head + ref + ptr_tail + reg
macro_rptr = rptr_head + reg + ptr_tail + reg

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
    ^ macro_func \
    ^ macro_struct \
    ^ macro_ds \
    ^ macro_fptr \
    ^ macro_rptr
    
statement = pp.Optional(label) + pp.Optional(comment) + cmd + pp.Optional(comment)
program = pp.ZeroOrMore(statement ^ comment ^ unknown)

def compile(in_filenames, out_filename):    
    # First pass
    first_pass = FPD()        
    for in_filename in in_filenames:
        lg.info("Processing {0}".format(in_filename))
        sfilename, _ = os.path.splitext(in_filename)
        first_pass.namespace = sfilename
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
