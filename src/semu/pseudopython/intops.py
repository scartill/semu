from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
from semu.pseudopython.expressions import PhyExpression
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b


@dataclass
class UOp(PhyExpression):
    operand: PhyExpression

    def __init__(
        self, pp_type: b.PPType, operand: PhyExpression, target: regs.Register
    ):
        super().__init__(pp_type, target)
        self.operand = operand

    def json(self):
        data = super().json()

        data.update({
            'Operand': self.operand.json()
        })

        return data


@dataclass
class Neg(UOp):
    def __init__(
        self, pp_type: b.PPType, operand: PhyExpression, target: regs.Register
    ):
        super().__init__(pp_type, operand, target)
        self.operand = operand

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


class BinOp(PhyExpression):
    left: PhyExpression
    right: PhyExpression

    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, target)
        self.left = left
        self.right = right

    def json(self):
        data = super().json()

        data.update({
            'Class': 'BinOp',
            'Left': self.left.json(),
            'Operator': self.op(),
            'Right': self.right.json()
        })

        return data

    def op(self) -> str:
        raise NotImplementedError()


@dataclass
class IntBinOp(BinOp):
    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, left, right, target)

    def json(self):
        data = super().json()

        data.update({
            'Class': 'IntBinOp',
            'Operator': self.op(),
        })

        return data

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


class Add(IntBinOp):
    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, left, right, target)

    def op(self):
        return 'add'


class Sub(IntBinOp):
    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, left, right, target)

    def op(self):
        return 'sub'


class Mul(IntBinOp):
    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, left, right, target)

    def op(self):
        return 'mul'


class Div(IntBinOp):
    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, left, right, target)

    def op(self):
        return 'div'


class Mod(IntBinOp):
    def __init__(
        self, pp_type: b.PPType, left: PhyExpression, right: PhyExpression,
        target: regs.Register
    ):
        super().__init__(pp_type, left, right, target)

    def op(self):
        return 'mod'
