import pyparsing as pp
import sys
import logging as lg
import struct

comment = pp.Literal("//") + pp.SkipTo("\n")

label = (pp.Word(pp.alphas) + pp.Suppress(':')).setParseAction(
	lambda r:
		print(r)
)

hlt_cmd = pp.Literal("hlt").setParseAction(
	lambda r:
		print(r)
)

nop_cmd = pp.Literal("nop").setParseAction(
	lambda r:
		print(r)
)

cmd = hlt_cmd \
	^ nop_cmd
	
statement = pp.Optional(label) + cmd
program = pp.ZeroOrMore(statement ^ comment)
	 
if(len(sys.argv) != 3):
    print("Usage: semuasm source.sasm binary")
    sys.exit(1)
	
lg.basicConfig(level = lg.DEBUG)
program.parseString(sys.argv[2])
