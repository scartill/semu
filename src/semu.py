#!/usr/bin/python3

import struct
import time
import sys
import logging as lg

import ops
import peripheral

from hwconf import *

EXIT_HALT = 0
EXIT_ASSERT_FAIL = 1
EXIT_LAUNCH_FAIL = 2
EXIT_EXEC_ERROR = 3

class Halt(Exception):
    pass
    
class Assert(Exception):
    pass

class Processor():
    def __init__(self):
        self.ip = 0     # Set when ROM is loaded
        self.sp = 0     # Set when lsp is called
        self.ii = 0x01  # Interrupt inhibit
        self.fp = 0     # Global code has no frame
        
        self.gp = [0] * 8
        
    ### Helpers ###
    
    def debug_dump(self):
        gps = str()
        for reg in self.gp:
            gps += "0x{0:X} ".format(reg)
        lg.debug("IP:{0:X} SP:{1:X} II:{2:X}, FP:{3:X}, [{4}]".format(self.ip, self.sp, self.ii, self.fp, gps))
    
    def next_fmt(self, fmt):
        global memory
        addr = self.ip 
        buf = memory[addr:addr + 4]
        (op,) = struct.unpack(fmt, buf)
        self.ip += 4
        return op

    def next_unsigned(self):
        return self.next_fmt(">I")

    def next_signed(self):
        return self.next_fmt(">i")
        
    def next(self):
        return self.next_unsigned()
        
    def set_next_gp(self, val):
        self.gp[self.next()] = val
        
    def get_next_gp(self):
        return self.gp[self.next()]
        
    def arithm_pair(self, op):
        a = self.get_next_gp()
        b = self.get_next_gp()
        self.set_next_gp(op(a, b))
            
    def do_push(self, val):
        global memory
        m = self.sp
        memory[m:m+4] = struct.pack(">I", val)
        self.sp += 4
        
    def do_pop(self):
        global memory
        self.sp -= 4
        m = self.sp
        (v,) = struct.unpack(">I", memory[m:m+4])
        return v
        
    ### Operations ###

    def nop(self):
        time.sleep(0.1)

    def hlt(self):
        raise Halt()

    def jmp(self):
        addr = self.get_next_gp()
        self.ip = addr

    def ldc(self):
        a = self.next()
        self.set_next_gp(a)

    def mrm(self):
        global memory   
        v = self.get_next_gp()
        m = self.get_next_gp()
        memory[m:m+4] = struct.pack(">I", v)

    def mmr(self):
        global memory   
        a = self.get_next_gp()
        (v,) = struct.unpack(">I", memory[a:a+4])
        self.set_next_gp(v)
        
    def out(self):
        global pp   
        l = self.get_next_gp()
        pp[l].signal()
        
    def jgt(self):
        val = self.get_next_gp()
        addr = self.get_next_gp()
        if(val > 0):
            self.ip = addr
    
    def opn(self):
        self.ii = 0
    
    def cls(self):
        self.ii = 1
    
    def ldr(self):
        a = self.ip      
        offset = self.next_signed()
        self.set_next_gp(a + offset)
        
    def lsp(self):
        self.sp = self.get_next_gp()
        
    def psh(self):
        val = self.get_next_gp()
        self.do_push(val)

    def pop(self):
        global memory
        v = self.do_pop()
        self.set_next_gp(v)
        
    def int(self):
        self.interrupt(0x00)
        
    def cll(self):
        ret_addr = self.ip + 4
        self.do_push(ret_addr)
        self.do_push(self.fp)
        self.fp = self.sp
        self.jmp()
        
    def ret(self):
        self.fp = self.do_pop()
        addr = self.do_pop()
        self.ip = addr
        
    def irx(self):
        self.fp = self.do_pop()
        for i in range(7, -1, -1):
            self.gp[i] = self.do_pop()
            
        addr = self.do_pop()
        self.ip = addr
        
        self.opn()
        
    def ssp(self):
        self.set_next_gp(self.sp)
        
    def mrr(self):
        val = self.get_next_gp()
        self.set_next_gp(val)
        
    def lla(self):
        offset = self.next_unsigned()
        self.set_next_gp(self.fp + offset)

    ### Arithmetic ###

    def inv(self):
        a = self.get_next_gp()
        self.set_next_gp(~a)

    def add(self): self.arithm_pair(lambda a, b: a + b)
    def sub(self): self.arithm_pair(lambda a, b: a - b)
    def mul(self): self.arithm_pair(lambda a, b: a * b)
    def div(self): self.arithm_pair(lambda a, b: a // b)
    def mod(self): self.arithm_pair(lambda a, b: a % b)
    def rsh(self): self.arithm_pair(lambda a, b: a >> b)
    def lsh(self): self.arithm_pair(lambda a, b: a << b)
    def bor(self): self.arithm_pair(lambda a, b: a | b)
    def xor(self): self.arithm_pair(lambda a, b: a ^ b)
    def band(self): self.arithm_pair(lambda a, b: a % b)
    
    def bpt(self):
        val = self.next_unsigned()    
        lg.debug("BREAKPOINT {0}".format(val))
        self.debug_dump()
        
    def aeq(self):
        a = self.get_next_gp()
        b = self.next_unsigned()
        
        lg.info("ASSERTION {0} <> {1}".format(a, b))
        
        if a != b:        
            raise Assert()
            
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

        ops.bpt  : bpt,
        ops.aeq  : aeq
    }
            
    ### Implementation ###
       
    def load_rom(self):
        global memory
        rom = open(sys.argv[1], "rb").read()  
        rb = rom_base
        l = len(rom)    
        memory[rb:rb+l] = rom
        self.ip = rom_base
        
    def interrupt(self, line):
        global memory
        
        #    lg.debug("INT {0}".format(line))
        
        # Inhibit interrupts
        self.cls()
        
        # Save registers    
        self.do_push(self.ip)
        for i in range(0, 8, 1):
            self.do_push(self.gp[i])
        self.do_push(self.fp)
        
        # Set handler's frame
        self.fp = self.sp
        
        # Find and a call a handler
        h_addr_inx = int_vect_base + line*4         # Interrupt handler address location
        (handler_addr,) = struct.unpack(">I", memory[h_addr_inx:h_addr_inx+4])
        self.ip = handler_addr
            
    def exec_next(self):
        op = self.next()
        handler = self.handlers[op]
        handler(self)
        
    def proc_int_queue(self):    
        global pp
        if(self.ii == 1):
            return

        for l, p in pp.items():        
            if(p.has_signal()):
                self.interrupt(l)
                break
                
    def cycle(self):
        self.exec_next()
        self.proc_int_queue()
            
    
### Global ###

def start_pp():
    for l, p in pp.items():
        p.start()

def stop_pp():
    for l, p in pp.items():
        p.stop()
        p.join()

def run():
    start_pp()
    proc.load_rom()
    
    try:
        while(True):
            proc.cycle()
    except Halt:
        lg.info("Execution halted gracefully")
        return EXIT_HALT
    except Assert:
        lg.info("Execution halted on false assertion")
        return EXIT_ASSERT_FAIL
    except Exception as e:
        lg.info("Execution halted on general error {0}".format(e))
        return EXIT_EXEC_ERROR
    finally:
        stop_pp()

### Entry point ###

memory = bytearray(memory_size)

# Line -> Device
pp = {
   #0 : loopback interrupt
    1 : peripheral.SysTimer(memory),
    2 : peripheral.Serial(memory)
}

proc = Processor()

if len(sys.argv) != 2:
    print("Usage: semu rom-binary")
    sys.exit(EXIT_LAUNCH_FAIL)

lg.basicConfig(level = lg.DEBUG)
lg.info("SEMU")

ec = run()
sys.exit(ec)



