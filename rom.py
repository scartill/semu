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

script = [
	ldc, 0x100F, reg0,
	lds, reg0,
	ldc, 65, reg0,
	psh, reg0,
	pop, reg1,
	hlt
]

bytes = semu_compile(script)
open("rom", "wb").write(bytearray(bytes))
