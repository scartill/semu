from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import JSON, Expression
import semu.pseudopython.registers as regs


@dataclass
class Unary(Expression):
    right: Expression


@dataclass
class Not(Unary):
    def emit(self) -> Sequence[str]:
        available = regs.get_available([
            self.target,
            self.right.target
        ])

        left_temp = available.pop()
        right_temp = available.pop()

        return flatten([
            '// Boolean Not',
            self.right.emit(),
            f'mrr {self.right.target} {right_temp}',
            f'ldc 1 {left_temp}',
            f'xor {left_temp} {right_temp} {self.target}',
        ])


@dataclass
class BoolOp(Expression):
    values: Sequence[Expression]

    def _initial(self) -> int:
        raise NotImplementedError()

    def _op(self) -> str:
        raise NotImplementedError()

    def emit(self) -> Sequence[str]:
        used: Sequence[regs.Register] = [value.target for value in self.values]
        used.append(self.target)
        available = regs.get_available(used)
        op_temp = available.pop()
        result_temp = available.pop()
        init = self._initial()
        op = self._op()

        return flatten([
            '// Boolean operator',
            f'ldc {init} {result_temp}',
            [
                [
                    f'push {result_temp}',
                    value.emit(),
                    f'pop {result_temp}',
                    f'mrr {value.target} {op_temp}',
                    f'{op} {result_temp} {op_temp} {result_temp}'
                ]
                for value in self.values
            ],
            f'mrr {result_temp} {self.target}',
            '// End boolean operator'
        ])

    def json(self) -> JSON:
        data = super().json()
        data['Values'] = [value.json() for value in self.values]
        data['Operator'] = self._op()
        return data


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
