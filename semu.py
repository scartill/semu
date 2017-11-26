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
	
		self.ip  = 0x00  # Instruction pointer
		self.ii  = 0x01  # Interrupt inhibit
		self.ret = 0x00  # Return pointer
		
		self.gp = {}
		for i in range(conf.gp_regs):
			self.gp[i] = 0x00
			
	def debug_dump(self):
		logging.debug(self.ppr.pformat((self.ip, self.ii, self.ret)))
		logging.debug(self.ppr.pformat(self.gp))
	
class Halt(Exception):
	pass

def next():
	global r	
	lb = r.ip + 4
	buf = memory[r.ip:lb]
	(op,) = struct.unpack(">I", buf)
	r.ip = lb
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
	m = r.gp[next()]
	memory[m:m+4] = struct.pack(">I", v)
	
def mmr():
	global r
	global memory	
	a = r.gp[next()]
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
	ops.cls  : cls
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
	r.ret = r.ip
	r.ip = conf.int_vect_base + line*4
	logging.debug("INT L:{0} D:{1} IP:{2:X}".format(line, word, r.ip))

def run():
	global r
	
	try:
		while(True):	
			exec_next()
			proc_int_queue()
			r.debug_dump()
	except Halt:
		logging.info("Execution halted")
	finally:
		stop_pp()

logging.basicConfig(level=logging.DEBUG)
start_pp()
reset()
run()
