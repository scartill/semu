import struct
import time
import logging as lg
from typing import Callable


import semu.common.ops as ops
from semu.runtime.peripheral import Peripherals

from semu.common.hwconf import ROM_BASE, INT_VECT_BASE, WORD_SIZE


class Halt(Exception):
    pass


class Assert(Exception):
    pass


class CPU():
    ip: int  # Instruction pointer
    sp: int  # Stack pointer
    ii: int  # Interrupt inhibit
    fp: int  # Frame pointer
    gp: list[int]  # General purpose registers

    def __init__(self, memory: bytearray, pp: Peripherals):
        self.memory = memory    # Ref. to memory
        self.pp = pp            # Ref. to Peripherals

        self.ip = ROM_BASE      # Execution start from the beginning of ROM
        self.sp = 0             # Set when lsp is called
        self.ii = 0x01          # Interrupt inhibit
        self.fp = 0             # Global code has no frame

        self.gp = [0] * 8

    # - Helpers - $

    def debug_dump(self):
        state = [f'{k}:{v:X}' for k, v in {
            'IP': self.ip,
            'SP': self.sp,
            'II': self.ii,
            'FP': self.fp
        }.items()]

        state.extend([f'{i}:{self.gp[i]:X}' for i in range(len(self.gp))])

        lg.debug(' '.join(state))

    def next_fmt(self, fmt: str):
        addr = self.ip
        buf = self.memory[addr:addr + WORD_SIZE]
        (op,) = struct.unpack(fmt, buf)
        self.ip += WORD_SIZE
        return op

    def next_unsigned(self) -> int:
        return self.next_fmt(">I")

    def next_signed(self) -> int:
        return self.next_fmt(">i")

    def next(self):
        return self.next_unsigned()

    def set_next_gp(self, val: int):
        self.gp[self.next()] = val

    def get_next_gp(self):
        return self.gp[self.next()]

    def arithm_pair(self, op: Callable[[int, int], int]):
        a = self.get_next_gp()
        b = self.get_next_gp()
        self.set_next_gp(op(a, b))

    def do_push(self, val: int):
        m = self.sp
        self.memory[m:m + WORD_SIZE] = struct.pack(">I", val)
        self.sp += WORD_SIZE

    def do_pop(self) -> int:
        self.sp -= WORD_SIZE
        m = self.sp
        (v,) = struct.unpack(">I", self.memory[m:m + WORD_SIZE])
        return v

    # - Operations - #

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
        self.memory[m:m + WORD_SIZE] = struct.pack(">I", v)

    def mmr(self):
        a = self.get_next_gp()
        (v,) = struct.unpack(">I", self.memory[a:a + WORD_SIZE])
        self.set_next_gp(v)

    def out(self):
        line = self.get_next_gp()
        self.pp[line].signal()

    def jgt(self):
        val = self.get_next_gp()
        addr = self.get_next_gp()

        if val > 0:
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

    def cll(self):
        ret_addr = self.ip + WORD_SIZE
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

    def intzero(self):
        self.interrupt(0x00)

    # - Arithmetic - $

    def inv(self):
        a = self.get_next_gp()
        self.set_next_gp(~a)

    def add(self):
        self.arithm_pair(lambda a, b: a + b)

    def sub(self):
        self.arithm_pair(lambda a, b: a - b)

    def mul(self):
        self.arithm_pair(lambda a, b: a * b)

    def div(self):
        self.arithm_pair(lambda a, b: a // b)

    def mod(self):
        self.arithm_pair(lambda a, b: a % b)

    def rsh(self):
        self.arithm_pair(lambda a, b: a >> b)

    def lsh(self):
        self.arithm_pair(lambda a, b: a << b)

    def bor(self):
        self.arithm_pair(lambda a, b: a | b)

    def xor(self):
        self.arithm_pair(lambda a, b: a ^ b)

    def band(self):
        self.arithm_pair(lambda a, b: a % b)

    def cpt(self):
        val = self.next_unsigned()
        message = f'CHECKPOINT {val}'
        lg.debug(message)
        self.debug_dump()
        # Write this to stdout so test engine can control execution
        print(message)

    def aeq(self):
        a = self.get_next_gp()
        b = self.next_unsigned()

        lg.info(f'ASSERTION {a} <> {b} ({a == b})')

        if a != b:
            raise Assert()

    HANDLERS = {
        ops.NOP: nop,
        ops.HLT: hlt,
        ops.JMP: jmp,
        ops.LDC: ldc,
        ops.MRM: mrm,
        ops.MMR: mmr,
        ops.OUT: out,
        ops.JGT: jgt,
        ops.OPN: opn,
        ops.CLS: cls,
        ops.LDR: ldr,
        ops.LSP: lsp,
        ops.PSH: psh,
        ops.POP: pop,
        ops.INT: intzero,
        ops.CLL: cll,
        ops.RET: ret,
        ops.IRX: irx,
        ops.SSP: ssp,
        ops.MRR: mrr,
        ops.LLA: lla,

        ops.INV: inv,
        ops.ADD: add,
        ops.SUB: sub,
        ops.MUL: mul,
        ops.DIV: div,
        ops.MOD: mod,
        ops.RSH: rsh,
        ops.LSH: lsh,
        ops.BOR: bor,
        ops.XOR: xor,
        ops.BAND: band,

        ops.CPT: cpt,
        ops.AEQ: aeq
    }

    # -- Implementation -- #

    def interrupt(self, line: int):
        if self.ii == 1:
            return

        # lg.debug("INT {0}".format(line))

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
        h_addr_inx = INT_VECT_BASE + line * WORD_SIZE         # Interrupt handler address location

        (handler_addr,) = struct.unpack(
            '>I',
            self.memory[h_addr_inx:h_addr_inx + WORD_SIZE]
        )

        self.ip = handler_addr

    def exec_next(self):
        op = self.next()
        handler = self.HANDLERS[op]
        handler(self)
