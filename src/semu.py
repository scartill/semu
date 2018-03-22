#!/usr/bin/python3

import struct
import time
import sys
import logging as lg

import ops
import peripheral

memory_size      = 0xFFFF
int_vect_base    = 0x0000
rom_base         = 0x0040

class Halt(Exception):
    pass

class Regs():
    def __init__(self):
        self.ip = 0     # Set when ROM is loaded
        self.sp = 0     # Set when lsp is called
        self.ii = 0x01  # Interrupt inhibit
        
        self.gp = [0] * 8
    
    def debug_dump(self):
        lg.debug("IP:{0} SP:{1} II:{2}, {3}".format(self.ip, self.sp, self.ii, self.gp))
    
### Helpers ###

def next_fmt(fmt):
    global r
    global memory
    addr = r.ip 
    buf = memory[addr:addr + 4]
    (op,) = struct.unpack(fmt, buf)
    r.ip += 4
    return op

def next_unsigned():
    return next_fmt(">I")

def next_signed():
    return next_fmt(">i")
    
def next():
    return next_unsigned()
    
def arithm_pair(op):
    global r
    a = r.gp[next()]
    b = r.gp[next()]
    r.gp[next()] = op(a, b)
        
def do_push(val):
    global r
    global memory
    m = r.sp
    memory[m:m+4] = struct.pack(">I", val)
    r.sp += 4
    
def do_pop():
    r.sp -= 4
    m = r.sp
    (v,) = struct.unpack(">I", memory[m:m+4])
    return v
    
### Operations ###

def nop():
    time.sleep(0.1)

def hlt():
    raise Halt()

def jmp():
    global r
    addr = r.gp[next()]
    r.ip = addr

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
    
def jgt():
    global r
    val = r.gp[next()]
    addr = r.gp[next()]
    if(val > 0):
        r.ip = addr
    
def opn():
    global r
    r.ii = 0

def cls():
    global r    
    r.ii = 1
    
def ldr():
    global r
    a = r.ip      
    offset = next_signed()
    r.gp[next()] = a + offset
    
def lsp():
    global r
    r.sp = r.gp[next()]
    
def psh():
    global r    
    val = r.gp[next()]
    do_push(val)

def pop():
    global r
    global memory
    v = do_pop()
    r.gp[next()] = v
    
def int():
    global r
    w = r.gp[next()]
    interrupt(0x00, w)
    
def cll():
    global r
    ret_addr = r.ip + 4
    do_push(ret_addr)
    jmp()
    
def ret():
    global r
    addr = do_pop()
    r.ip = addr
    
def irx():
    global r
    for i in range(7, -1, -1):
        r.gp[i] = do_pop()
    ret()
    opn()
    
def ssp():
    global r
    r.gp[next()] = r.sp
    
def mrr():
    global r
    val = r.gp[next()]
    r.gp[next()] = val

### Arithmetic ###

def inv():
    global r
    a = r.gp[next()]
    r.gp[next()] = ~a

def add(): arithm_pair(lambda a, b: a + b)
def sub(): arithm_pair(lambda a, b: a - b)
def mul(): arithm_pair(lambda a, b: a * b)
def div(): arithm_pair(lambda a, b: a // b)
def mod(): arithm_pair(lambda a, b: a % b)
def rsh(): arithm_pair(lambda a, b: a >> b)
def lsh(): arithm_pair(lambda a, b: a << b)
def bor(): arithm_pair(lambda a, b: a | b)
def xor(): arithm_pair(lambda a, b: a ^ b)
def band(): arithm_pair(lambda a, b: a % b)
    
### Emulated ###

def bpt():
    val = next_unsigned()    
    lg.debug("BREAKPOINT {0}".format(val))
    r.debug_dump()
    
### Implementation ###

handlers = {
    ops.nop  : nop,
    ops.hlt  : hlt,
    ops.jmp  : jmp,    
    ops.ldc  : ldc,
    ops.mrm  : mrm,
    ops.mmr  : mmr,
    ops.out  : out,
    ops.jgt  : jgt,    
    ops.opn  : opn,
    ops.cls  : cls,
    ops.ldr  : ldr,
    ops.lsp  : lsp,
    ops.psh  : psh,
    ops.pop  : pop,
    ops.int  : int,
    ops.cll  : cll,
    ops.ret  : ret,
    ops.irx  : irx,    
    ops.ssp  : ssp,
    ops.mrr  : mrr,
    
    ops.inv  : inv,
    ops.add  : add,
    ops.sub  : sub,
    ops.mul  : mul,
    ops.div  : div,
    ops.mod  : mod,
    ops.rsh  : rsh,
    ops.lsh  : lsh,
    ops.bor  : bor,
    ops.xor  : xor,
    ops.band : band,

    ops.bpt  : bpt
}

# Line -> Device
pp = {
   #0 : loopback interrupt
    1 : peripheral.SysTimer(),
    2 : peripheral.Serial()
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
    memory = bytearray(memory_size)

def load_rom():
    global r
    global memory
    rom = open(sys.argv[1], "rb").read()  
    rb = rom_base
    l = len(rom)    
    memory[rb:rb+l] = rom
    r.ip = rom_base

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
    global memory
    
#    lg.debug("INT {0} {1}".format(line, word))
    
    cls()
    do_push(r.ip)
    for i in range(0, 8, 1):
        do_push(r.gp[i])
    r.gp[0] = word                         # Passing int word in 'a'
    h_addr_inx = int_vect_base + line*4    # Interrupt handler address location
    (handler_addr,) = struct.unpack(">I", memory[h_addr_inx:h_addr_inx+4])
    r.ip = handler_addr

def run():
    global r

    start_pp()
    reset()
    
    try:
        while(True):    
            exec_next()
            proc_int_queue()
    except Halt:
        lg.info("Execution halted")
    finally:
        stop_pp()

if len(sys.argv) != 2:
    print("Usage: semu rom-binary")
    sys.exit(1)

lg.basicConfig(level = lg.DEBUG)
lg.info("SEMU")
run()
