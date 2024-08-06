from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression
import semu.pseudopython.registers as regs


@dataclass
class UOp(Expression):
    operand: Expression


@dataclass
class Neg(UOp):
    def emit(self):
        temp = regs.get_temp([
            self.target,
            self.operand.target
        ])

        return flatten([
            f'// UOp begin to reg:{self.target}',
            f'push {temp}',
            self.operand.emit(),
            f'ldc -1 {temp}',
            f'mul {temp} {self.operand.target} {self.target}',
            f'pop {temp}',
            '// UOp end'
        ])


@dataclass
class BinOp(Expression):
    left: Expression
    right: Expression

    def op(self) -> str:
        raise NotImplementedError()


@dataclass
class IntBinOp(BinOp):
    def emit(self):
        available = regs.get_available([
            self.target,
            self.left.target,
            self.right.target
        ])

        left_temp = available.pop()
        right_temp = available.pop()

        return flatten([
            f'// BinOp begin to reg:{self.target}',
            f'push {left_temp}',
            f'push {right_temp}',
            self.left.emit(),
            f'mrr {self.left.target} {left_temp}',
            self.right.emit(),
            f'mrr {self.right.target} {right_temp}',
            f'{self.op()} {left_temp} {right_temp} {self.target}',
            f'pop {right_temp}',
            f'pop {left_temp}',
            '// BinOp end'
        ])


@dataclass
class Add(IntBinOp):
    def op(self):
        return 'add'


@dataclass
class Sub(IntBinOp):
    def op(self):
        return 'sub'


@dataclass
class Mul(IntBinOp):
    def op(self):
        return 'mul'


@dataclass
class Div(IntBinOp):
    def op(self):
        return 'div'


@dataclass
class Mod(IntBinOp):
    def op(self):
        return 'mod'
