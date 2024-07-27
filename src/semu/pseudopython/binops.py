from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, REGISTERS


@dataclass
class BinOp(Expression):
    left: Expression
    right: Expression

    def op(self) -> str:
        raise NotImplementedError()


@dataclass
class UIntBinOp(BinOp):
    def emit(self):
        print(self)
        available = set(REGISTERS.copy())
        available.discard(self.target)
        available.discard(self.left.target)
        available.discard(self.right.target)
        print('AV', available)
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
class Add(UIntBinOp):
    def op(self):
        return 'add'


@dataclass
class Sub(UIntBinOp):
    def op(self):
        return 'sub'


@dataclass
class Mul(UIntBinOp):
    def op(self):
        return 'sub'


@dataclass
class Div(UIntBinOp):
    def op(self):
        return 'div'

@dataclass
class Mod(UIntBinOp):
    def op(self):
        return 'mod'
