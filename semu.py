import struct
import time
import logging 

import ops
import peripheral
import semuconf as cf

class Regs():
	def __init__(self):
		self.ip  = 0x00  # Instruction pointer
		self.ii  = 0x01  # Interrupt inhibit
		self.sp  = 0x00  # Stack pointer
		
		self.gp = [0] * cf.gp_regs 
			
	def debug_dump(self):
		logging.debug("IP:{0:X} SP:{1:X} II:{2}".format(self.ip, self.sp, self.ii))
		logging.debug(self.gp)
	
class Halt(Exception):
	pass

def next():
	global r
	addr = r.ip	
	buf = memory[addr:addr + 4]
	(op,) = struct.unpack(">I", buf)
	r.ip += 4
	return op
	
def nop():
	time.sleep(1.0)
	
def hlt():
	raise Halt()
	
def jmp():
	global r
	addr = r.gp[next()]
	r.ip = addr
	
def add():
	global r
	a = r.gp[next()]
	b = r.gp[next()]
	r.gp[next()] = a + b
	
def ldc():
	global r
	a = next()
	r.gp[next()] = a
	
def mrm():
	global r
	global memory	
	v = r.gp[next()]
	m = r.gp[next()]
	memory[m:m+4] = struct.pack(">I", v)
	
def mmr():
	global r
	global memory	
	a = r.gp[next()]
	(v,) = struct.unpack(">I", memory[a:a+4])
	r.gp[next()] = v
	
def out():
	global r
	global pp	
	w = r.gp[next()]
	l = r.gp[next()]
	pp[l].send_word(w)
	
def jne():
	global r
	val = r.gp[next()]
	addr = r.gp[next()]
	if(val != 0):
		r.ip = addr
		
def sub():
	global r
	v1 = r.gp[next()]
	v2 = r.gp[next()]
	r.gp[next()] = v1 - v2
	
def opn():
	global r
	r.ii = 0

def cls():
	global r	
	r.ii = 1
	
def ldr():
	global r
	a = r.ip - 4 # ldr instruction address
	offset = signed_next()
	r.gp[next()] = a + offset
	
def lds():
	global r
	r.sp = r.gp[next()]
	
def do_push(val):
	global r
	global memory
	m = r.sp
	memory[m:m+4] = struct.pack(">I", val)
	r.sp += 4
	
def psh():
	global r	
	val = r.gp[next()]
	do_push(val)
	
def do_pop():
	r.sp -= 4
	m = r.sp
	(v,) = struct.unpack(">I", memory[m:m+4])
	return v

def pop():
	global r
	global memory
	v = do_pop()
	r.gp[next()] = v	
	
def int():
	global r
	w = r.gp[next()]
	interrupt(0x00, w)
	
handlers = {
	ops.nop  : nop,
	ops.hlt  : hlt,
	ops.jmp  : jmp,
	ops.add  : add,
	ops.ldc  : ldc,
	ops.mrm  : mrm,
	ops.mmr  : mmr,
	ops.out  : out,
	ops.jne	 : jne,
	ops.sub	 : sub,
	ops.opn	 : opn,
	ops.cls  : cls,
	ops.ldr  : ldr,
	ops.lds  : lds,
	ops.psh  : psh,
	ops.pop  : pop,
	ops.int  : int
}

# Line -> Device
pp = { 
	ops.inttime : peripheral.SysTimer(),
	ops.intser  : peripheral.Serial()
}

def start_pp():
	for l, p in pp.items():
		p.start()

def stop_pp():
	for l, p in pp.items():
		p.send_stop()
		p.join()

def init_registers():
	global r
	r = Regs()	
	
def init_memory():
	global memory
	memory = bytearray(cf.memory_size)
	
def load_rom():
	global memory
	rom = open("rom", "rb").read()	
	rb = cf.rom_base
	l = len(rom)	
	memory[rb:rb+l] = rom		

def reset():
	init_registers()
	init_memory()	
	load_rom()
	
def exec_next():
	op = next()
	handler = handlers[op]
	handler()
	
def proc_int_queue():
	global r
	
	if(r.ii == 1):
		return

	for l, p in pp.items():
		w = p.peek()		
		if(w != None):
			interrupt(l, w)
			break
			
def save_ctxt():
	global r
	cls()
	do_push(r.ip)	
	for i in range(0,8,1):
		do_push(r.gp[i])
			
def restore_ctxt():
	global r
	for i in range(7,-1,-1):
		r.gp[i] = do_pop()	
	r.ip = do_pop()
			
def interrupt(line, word):
	save_ctxt()
	r.ip = cf.int_vect_base + line*4
	logging.debug("INT L:{0} D:{1} IP:{2:X}".format(line, word, r.ip))

def run():
	global r

	start_pp()
	reset()
	
	try:
		while(True):	
			exec_next()
			proc_int_queue()
			r.debug_dump()
	except Halt:
		logging.info("Execution halted")
	finally:
		stop_pp()

logging.basicConfig(level = logging.DEBUG)
run()
