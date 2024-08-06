from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Element, Expression
import semu.pseudopython.registers as regs


@dataclass
class CompareOp(Element):
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
class Compare(Expression):
    left: Expression
    op: CompareOp
    right: Expression

    def __init__(self, target: regs.Register, left: Expression, op: CompareOp, right: Expression):
        super().__init__(target_type='bool32', target=target)
        self.left = left
        self.op = op
        self.right = right

    def emit(self) -> Sequence[str]:
        l_target = self.left.target
        r_target = self.right.target
        assert l_target != r_target

        available = regs.get_available([
            self.target,
            l_target,
            r_target
        ])

        address = available.pop()
        temp = available.pop()

        label_true = self._make_label('true')
        label_false = self._make_label('false')
        label_end = self._make_label('end')

        return flatten([
            '// Compare',
            f'push {address}',
            f'push {temp}',
            self.left.emit(),
            self.right.emit(),
            self.op.emit(l_target, r_target, address, temp, label_true, label_false),
            f'{label_false}:',
            f'ldc 0 {self.target}',
            f'ldr &{label_end} {address}',
            f'jmp {address}',
            f'{label_true}:',
            f'ldc 1 {self.target}',
            f'{label_end}:',
            f'pop {temp}',
            f'pop {address}',
            '// End Compare'
        ])
