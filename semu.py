import struct
import time
import logging 
import pprint

import ops
import peripheral

import semuconf as conf

class Regs():
	def __init__(self):
		self.ppr = pprint.PrettyPrinter(indent = 4)
	
		self.bp  = 0x00  # Base pointer
		self.ip  = 0x00  # Instruction pointer
		self.ii  = 0x01  # Interrupt inhibit
		self.sp  = 0x00  # Stack pointer
		
		self.gp = [0] * conf.gp_regs 
			
	def debug_dump(self):
		logging.debug("IP:{0:X} SP:{1:X} BP:{2:X} II:{3}".format(self.ip, self.sp, self.bp, self.ii))
		logging.debug(self.ppr.pformat(self.gp))
	
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
	time.sleep(0.1)
	
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
	m = r.bp + r.gp[next()]
	memory[m:m+4] = struct.pack(">I", v)
	
def mmr():
	global r
	global memory	
	a = r.bp + r.gp[next()]
	(v,) = struct.unpack(">I", memory[a:a+4])
	r.gp[next()] = v
	
def int():
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
	
def ldb():
	global r
	r.bp = r.gp[next()]
	
def lds():
	global r
	r.sp = r.gp[next()]	
	
def psh():
	global r
	global memory	
	v = r.gp[next()]
	m = r.sp
	print((v, m))
	memory[m:m+4] = struct.pack(">I", v)
	r.sp += 4

def pop():
	global r
	global memory
	r.sp -= 4
	m = r.sp
	(v,) = struct.unpack(">I", memory[m:m+4])
	r.gp[next()] = v	
	
handlers = {
	ops.nop  : nop,
	ops.hlt  : hlt,
	ops.jmp  : jmp,
	ops.add  : add,
	ops.ldc  : ldc,
	ops.mrm  : mrm,
	ops.mmr  : mmr,
	ops.int  : int,
	ops.jne	 : jne,
	ops.sub	 : sub,
	ops.opn	 : opn,
	ops.cls  : cls,
	ops.ldb  : ldb,
	ops.lds  : lds,
	ops.psh  : psh,
	ops.pop  : pop
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
	memory = bytearray(conf.memory_size)
	
def load_rom():
	global memory
	rom = open("rom", "rb").read()	
	rb = conf.rom_base
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
			
def interrupt(line, word):
	global r
	cls()
	r.ip = conf.int_vect_base + line*4
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
