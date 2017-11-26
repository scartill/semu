from ops import *
from itertools import chain
import struct

def elem_bytes(elem):
	if(isinstance(elem, list)):
		bytes = semu_compile(elem)
	else:
		bytes = struct.pack(">I", elem)
		
	return bytes

def semu_compile(script):
	code = bytearray()
	for elem in script:
		code += elem_bytes(elem)
	
	return code
	
init_timer = [
	ldc, 1, reg0,
	ldc, inttime, reg1,
	int, reg0, reg1
]

reset = [
	ldc, 0, reg0,
	nop,
	jmp, reg0
]

script = [
	#opn,
	#init_timer,
	reset,
	hlt
]

bytes = semu_compile(script)
open("rom", "wb").write(bytearray(bytes))
