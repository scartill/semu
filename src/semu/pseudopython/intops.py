from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import PhysicalExpression
import semu.pseudopython.registers as regs


@dataclass
class UOp(PhysicalExpression):
    operand: PhysicalExpression

    def json(self):
        data = super().json()

        data.update({
            'Operand': self.operand.json()
        })

        return data


@dataclass
class Neg(UOp):
    def emit(self):
        temp = regs.get_temp([
            self.target,
            self.operand.target
        ])

        return flatten([
            f'// UOp begin to reg:{self.target}',
            self.operand.emit(),
            f'ldc -1 {temp}',
            f'mul {temp} {self.operand.target} {self.target}',
            '// UOp end'
        ])


@dataclass
class BinOp(PhysicalExpression):
    left: PhysicalExpression
    right: PhysicalExpression

    def json(self):
        data = super().json()

        data.update({
            'Left': self.left.json(),
            'Operator': self.op(),
            'Right': self.right.json()
        })

        return data

    def op(self) -> str:
        raise NotImplementedError()


@dataclass
class IntBinOp(BinOp):
    def emit(self):
        l_target = self.left.target
        r_target = self.right.target
        target = self.target

        return flatten([
            f'// BinOp begin to reg:{target}',
            self.left.emit(),
            f'push {l_target}',
            self.right.emit(),
            f'pop {l_target}',
            f'{self.op()} {l_target} {r_target} {target}',
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
