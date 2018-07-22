#!/usr/bin/python3

import struct
import time
import sys
import logging as lg

import ops
import peripheral

from hwconf import *

memory = bytearray(memory_size)

class Halt(Exception):
    pass

class Regs():
    def __init__(self):
        self.ip = 0     # Set when ROM is loaded
        self.sp = 0     # Set when lsp is called
        self.ii = 0x01  # Interrupt inhibit
        self.fp = 0     # Global code has no frame
        
        self.gp = [0] * 8
    
    def debug_dump(self):
        gps = str()
        for reg in self.gp:
            gps += "0x{0:X} ".format(reg)
        lg.debug("IP:{0:X} SP:{1:X} II:{2:X}, FP:{3:X}, [{4}]".format(self.ip, self.sp, self.ii, self.fp, gps))
    
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
    l = r.gp[next()]
    pp[l].signal()
    
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
    interrupt(0x00)
    
def cll():
    global r
    ret_addr = r.ip + 4
    do_push(ret_addr)
    do_push(r.fp)
    r.fp = r.sp
    jmp()
    
def ret():
    global r
    r.fp = do_pop()
    addr = do_pop()
    r.ip = addr
    
def irx():
    global r
    
    r.fp = do_pop()
    for i in range(7, -1, -1):
        r.gp[i] = do_pop()
        
    addr = do_pop()
    r.ip = addr
    
    opn()
    
def ssp():
    global r
    r.gp[next()] = r.sp
    
def mrr():
    global r
    val = r.gp[next()]
    r.gp[next()] = val
    
def lla():
    global r
    offset = next_unsigned()
    r.gp[next()] = r.fp + offset

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
    ops.lla  : lla,
    
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
    1 : peripheral.SysTimer(memory),
    2 : peripheral.Serial(memory)
}
    
def start_pp():
    for l, p in pp.items():
        p.start()

def stop_pp():
    for l, p in pp.items():
        p.stop()
        p.join()

def init_registers():
    global r
    r = Regs()
    
def load_rom():
    global r
    global memory
    rom = open(sys.argv[1], "rb").read()  
    rb = rom_base
    l = len(rom)    
    memory[rb:rb+l] = rom
    r.ip = rom_base

def setup():
    init_registers()
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
        if(p.has_signal()):
            interrupt(l)
            break
    
def interrupt(line):
    global r
    global memory
    
#    lg.debug("INT {0}".format(line))
    
    # Inhibit interrupts
    cls()
    
    # Save registers    
    do_push(r.ip)
    for i in range(0, 8, 1):
        do_push(r.gp[i])
    do_push(r.fp)
    
    # Set handler's frame
    r.fp = r.sp
    
    # Find and a call a handler
    h_addr_inx = int_vect_base + line*4         # Interrupt handler address location
    (handler_addr,) = struct.unpack(">I", memory[h_addr_inx:h_addr_inx+4])
    r.ip = handler_addr

def run():
    global r

    start_pp()
    setup()
    
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
