from ops import *
from itertools import chain

def word(val):
	return [0, 0, 0, val] # big-endian

script = [
	opn,
	ldc, 0, reg0,
	nop,
	jmp, reg0,
	hlt
]

bytes = list(chain.from_iterable([word(val) for val in script]))
open("rom", "wb").write(bytearray(bytes))
