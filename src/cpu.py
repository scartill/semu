import struct
import time
import logging as lg

import ops

from hwconf import *

class Halt(Exception):
    pass
    
class Assert(Exception):
    pass

class CPU():
    def __init__(self, memory, pp):
        self.memory = memory    # Ref. to memory
        self.pp = pp            # Ref. to PERIPHERALS
    
        self.ip = ROM_BASE      # Execution start from the beginning of ROM
        self.sp = 0             # Set when lsp is called
        self.ii = 0x01          # Interrupt inhibit
        self.fp = 0             # Global code has no frame
        
        self.gp = [0] * 8
        
    ### Helpers ###
    
    def debug_dump(self):
        gps = str()
        for reg in self.gp:
            gps += "0x{0:X} ".format(reg)
        lg.debug("IP:{0:X} SP:{1:X} II:{2:X}, FP:{3:X}, [{4}]".format(self.ip, self.sp, self.ii, self.fp, gps))
    
    def next_fmt(self, fmt):
        addr = self.ip 
        buf = self.memory[addr:addr + 4]
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
        m = self.sp
        self.memory[m:m+4] = struct.pack(">I", val)
        self.sp += 4
        
    def do_pop(self):
        self.sp -= 4
        m = self.sp
        (v,) = struct.unpack(">I", self.memory[m:m+4])
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
        v = self.get_next_gp()
        m = self.get_next_gp()
        self.memory[m:m+4] = struct.pack(">I", v)

    def mmr(self):
        a = self.get_next_gp()
        (v,) = struct.unpack(">I", self.memory[a:a+4])
        self.set_next_gp(v)
        
    def out(self):
        l = self.get_next_gp()
        self.pp[l].signal()
        
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

    def interrupt(self, line):   
        if(self.ii == 1):
            return
        
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
        h_addr_inx = INT_VECT_BASE + line*4         # Interrupt handler address location
        (handler_addr,) = struct.unpack(">I", self.memory[h_addr_inx:h_addr_inx+4])
        self.ip = handler_addr
            
    def exec_next(self):
        op = self.next()
        handler = self.handlers[op]
        handler(self)
