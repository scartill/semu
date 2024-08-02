from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, Register


class CompareOp:
    def prepare(self, left: Register, right: Register):
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
    def prepare(self, left: Register, right: Register):
        return [
            '// Greater Than',
            f'sub {left} {right} {left}',
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
        label_true = self._make_label('true')
        label_false = self._make_label('false')
        label_end = self._make_label('end')

        return flatten([
            '// Compare',
            f'push {address}',
            self.left.emit(),
            self.right.emit(),
            self.op.prepare(self.left.target, self.right.target),
            f'ldr &{label_true} {address}',
            f'jgt {self.left.target} {address}',
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
