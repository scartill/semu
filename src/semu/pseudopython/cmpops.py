from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
import semu.pseudopython.base as b
import semu.pseudopython.expressions as ex
import semu.pseudopython.pptypes as t
import semu.pseudopython.registers as regs


@dataclass
class CompareOp(b.Element):
    def json(self):
        data = super().json()
        data.update({'Type': 'compare'})
        return data

    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        raise NotImplementedError()


class Eq(CompareOp):
    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        return [
            '// Equal',
            f'sub {left} {right} {temp}',
            f'ldr &{label_false} {address}',
            f'jgt {temp} {address}',
            f'ldc -1 {left}',
            f'mul {temp} {left} {temp}',
            f'jgt {temp} {address}',
            f'ldr &{label_true} {address}',
            f'jmp {address}'
        ]


class NotEq(CompareOp):
    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        return [
            '// Equal',
            f'sub {left} {right} {temp}',
            f'ldr &{label_true} {address}',
            f'jgt {temp} {address}',
            f'ldc -1 {left}',
            f'mul {temp} {left} {temp}',
            f'jgt {temp} {address}',
            f'ldr &{label_false} {address}',
            f'jmp {address}'
        ]


class Lt(CompareOp):
    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        return [
            '// Less Than',
            f'ldc -1 {temp}',
            f'mul {left} {temp} {left}',
            f'mul {right} {temp} {right}',
            f'sub {left} {right} {left}',
            f'ldr &{label_true} {address}',
            f'jgt {left} {address}',
            f'ldr &{label_false} {address}',
            f'jmp {address}',
        ]


class LtE(CompareOp):
    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        return [
            '// Less Than or Equal',
            f'ldc -1 {temp}',
            f'mul {left} {temp} {left}',
            f'mul {right} {temp} {right}',
            f'sub {left} {right} {temp}',
            f'ldr &{label_true} {address}',
            f'jgt {temp} {address}',
            f'ldc -1 {left}',
            f'mul {temp} {left} {temp}',
            f'ldr &{label_false} {address}',
            f'jgt {temp} {address}',
            f'ldr &{label_true} {address}',
            f'jmp {address}',
        ]


@dataclass
class Gt(CompareOp):
    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        return [
            '// Greater Than',
            f'sub {left} {right} {left}',
            f'ldr &{label_true} {address}',
            f'jgt {left} {address}',
            f'ldr &{label_false} {address}',
            f'jmp {address}',
        ]


class GtE(CompareOp):
    def emit(
        self,
        left: regs.Register, right: regs.Register,
        address: regs.Register, temp: regs.Register,
        label_true: str, label_false: str
    ):
        return [
            '// Greater Than or Equal',
            f'sub {left} {right} {temp}',
            f'ldr &{label_true} {address}',
            f'jgt {temp} {address}',
            f'ldc -1 {left}',
            f'mul {temp} {left} {temp}',
            f'ldr &{label_false} {address}',
            f'jgt {temp} {address}',
            f'ldr &{label_true} {address}',
            f'jmp {address}',
        ]


@dataclass
class Compare(ex.PhyExpression):
    left: ex.PhyExpression
    op: CompareOp
    right: ex.PhyExpression

    def __init__(
        self, target: regs.Register,
        left: ex.PhyExpression, op: CompareOp, right: ex.PhyExpression
    ):
        super().__init__(pp_type=t.Bool32, target=target)
        self.left = left
        self.op = op
        self.right = right

    def json(self):
        data = super().json()

        data.update({
            'Left': self.left.json(),
            'Operator': self.op.json(),
            'Right': self.right.json()
        })

        return data

    def emit(self) -> Sequence[str]:
        l_target = self.left.target
        r_target = self.right.target

        available = regs.get_available([
            self.target,
            l_target,
            r_target
        ])

        address = available.pop()
        l_temp = available.pop()
        temp = available.pop()
        label_true = self._make_label('true')
        label_false = self._make_label('false')
        label_end = self._make_label('end')

        return flatten([
            '// Compare',
            self.left.emit(),
            f'push {l_target}',
            self.right.emit(),
            f'pop {l_temp}',
            self.op.emit(l_temp, r_target, address, temp, label_true, label_false),
            f'{label_false}:',
            f'ldc 0 {self.target}',
            f'ldr &{label_end} {address}',
            f'jmp {address}',
            f'{label_true}:',
            f'ldc 1 {self.target}',
            f'{label_end}:',
            '// End Compare'
        ])
