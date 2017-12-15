import pyparsing as pp
import sys
import logging as lg
import struct

import ops

fst_pass_list = None	# Global 1st pass results

def issue_word(fmt, word):
	global fst_pass_list
	bytes = struct.pack(fmt, word)
	fst_pass_list.append(('bytes', bytes))

def issue_usigned(word):
	issue_word(">I", word)

def issue_op(op):
	lg.debug("Issuing command 0x{0:X}".format(op))
	issue_usigned(op)
	
def on_label():
	pass
	
def on_reg(val):
	issue_usigned(val)
	
def g_cmd(literal, op):
	return pp.Literal(literal).setParseAction(lambda _: issue_op(op))
	
def g_reg(reg_name, reg_num):
	return pp.Literal(reg_name).setParseAction(lambda _: on_reg(reg_num))
	
comment = pp.Literal("//") + pp.SkipTo("\n")
label = (pp.Word(pp.alphas) + pp.Suppress(':')).setParseAction(on_label)
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
us_dec_const = pp.Regex("[0-9]+").setParseAction(lambda r: issue_usigned(int(r[0])))
us_const = us_dec_const
hlt_cmd = g_cmd("hlt", ops.hlt)
nop_cmd = g_cmd("nop", ops.nop)
jmp_cmd = g_cmd("jmp", ops.jmp) + reg
add_cmd = g_cmd("add", ops.add) + reg + reg + reg
ldc_cmd = g_cmd("ldc", ops.ldc) + us_dec_const + reg
mrm_cmd = g_cmd("mrm", ops.mrm) + reg + reg
mmr_cmd = g_cmd("mmr", ops.mmr) + reg + reg
cmd = hlt_cmd \
	^ nop_cmd \
	^ jmp_cmd \
	^ add_cmd \
	^ ldc_cmd \
	^ mrm_cmd \
	^ mmr_cmd
statement = pp.Optional(label) + cmd
program = pp.ZeroOrMore(statement ^ comment)

def compile(in_filename, out_filename):
	global fst_pass_list
	
	fst_pass_list = list()
	program.parseFile(in_filename)
	bytes = bytearray()
	
	for (t, d) in fst_pass_list:
		if(t == 'bytes'):
			bytes += d
	
	open(out_filename, "wb").write(bytes)
	
	 
if(len(sys.argv) != 3):
    print("Usage: semuasm source.sasm binary")
    sys.exit(1)
	
lg.basicConfig(level = lg.DEBUG)
lg.info("SEMU ASM")
compile(sys.argv[1], sys.argv[2])
