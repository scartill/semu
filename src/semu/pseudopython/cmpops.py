from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, Register


class CompareOp:
    def emit(
            self,
            left: Register, right: Register, address: Register, temp: Register,
            label_true: str, label_false: str
    ):
        raise NotImplementedError()


class Eq(CompareOp):
    pass


class NotEq(CompareOp):
    pass


class Lt(CompareOp):
    pass


class LtE(CompareOp):
    pass


class Gt(CompareOp):
    def emit(
            self,
            left: Register, right: Register, address: Register, temp: Register,
            label_true: str, label_false: str
    ):
        return [
            '// Greater Than',
            f'sub {left} {right} {temp}',
            f'ldr &{label_true} {address}',
            f'jgt {temp} {address}',
        ]


class GtE(CompareOp):
    pass


@dataclass
class Compare(Expression):
    left: Expression
    op: CompareOp
    right: Expression

    def __init__(self, target: Register, left: Expression, op: CompareOp, right: Expression):
        super().__init__(target_type='bool32', target=target)
        self.left = left
        self.op = op
        self.right = right

    def emit(self) -> Sequence[str]:
        available = self._get_available_registers([
            self.target,
            self.left.target,
            self.right.target
        ])

        address = available.pop()
        temp = available.pop()

        label_true = self._make_label('true')
        label_false = self._make_label('false')
        label_end = self._make_label('end')

        l_target = self.left.target
        r_target = self.right.target

        return flatten([
            '// Compare',
            f'push {address}',
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
            f'pop {address}',
            '// End Compare'
        ])
