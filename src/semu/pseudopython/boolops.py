from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, Register


@dataclass
class Unary(Expression):
    right: Expression


@dataclass
class Not(Unary):
    def emit(self) -> Sequence[str]:
        available = self._get_available_registers([
            self.target,
            self.right.target
        ])

        left_temp = available.pop()
        right_temp = available.pop()

        return flatten([
            '// Boolean Not',
            f'push {left_temp}',
            f'push {right_temp}',
            self.right.emit(),
            f'mrr {self.right.target} {right_temp}',
            f'ldc 1 {left_temp}',
            f'xor {left_temp} {right_temp} {self.target}',
            f'pop {right_temp}',
            f'pop {left_temp}',
        ])


@dataclass
class BoolOp(Expression):
    values: Sequence[Expression]

    def _initial(self) -> int:
        raise NotImplementedError()

    def _op(self) -> str:
        raise NotImplementedError()

    def emit(self) -> Sequence[str]:
        used: Sequence[Register] = [value.target for value in self.values]
        used.append(self.target)
        available = self._get_available_registers(used)
        op_temp = available.pop()
        result_temp = available.pop()
        init = self._initial()
        op = self._op()

        return flatten([
            '// Boolean operator',
            f'push {op_temp}',
            f'push {result_temp}',
            f'ldc {init} {result_temp}',
            [
                [
                    value.emit(),
                    f'mrr {value.target} {op_temp}',
                    f'{op} {result_temp} {op_temp} {result_temp}'
                ]
                for value in self.values
            ],
            f'mrr {result_temp} {self.target}',
            f'pop {result_temp}',
            f'pop {op_temp}',
            '// End boolean operator'
        ])


@dataclass
class And(BoolOp):
    def _initial(self) -> int:
        return 1

    def _op(self) -> str:
        return 'and'


@dataclass
class Or(BoolOp):
    def _initial(self) -> int:
        return 0

    def _op(self) -> str:
        return 'or'
