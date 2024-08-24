from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import PhyExpression
import semu.pseudopython.base as b
import semu.pseudopython.registers as regs


@dataclass
class Unary(PhyExpression):
    operand: PhyExpression

    def __init__(
        self, pp_type: b.PPType, operand: PhyExpression, target: regs.Register
    ):
        super().__init__(pp_type, target)
        self.operand = operand

    def json(self):
        data = super().json()
        data['Class'] = 'Unary'
        data['Right'] = self.operand.json()
        return data


@dataclass
class Not(Unary):
    def __init__(
        self, pp_type: b.PPType, operand: PhyExpression, target: regs.Register
    ):
        super().__init__(pp_type, operand, target)

    def json(self):
        data = super().json()
        data['Class'] = 'Not'
        return data

    def emit(self) -> Sequence[str]:
        available = regs.get_available([
            self.target,
            self.operand.target
        ])

        left_temp = available.pop()
        right_temp = available.pop()

        return flatten([
            '// Boolean Not',
            self.operand.emit(),
            f'mrr {self.operand.target} {right_temp}',
            f'ldc 1 {left_temp}',
            f'xor {left_temp} {right_temp} {self.target}',
        ])


@dataclass
class BoolOp(PhyExpression):
    values: Sequence[PhyExpression]

    def __init__(
        self, pp_type: b.PPType, values: Sequence[PhyExpression],
        target: regs.Register
    ):
        super().__init__(pp_type, target)
        self.values = values

    def _initial(self) -> int:
        raise NotImplementedError()

    def _op(self) -> str:
        raise NotImplementedError()

    def json(self):
        data = super().json()
        data['Class'] = 'BoolOp'
        data['Values'] = [value.json() for value in self.values]
        data['Operator'] = self._op()
        return data

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


@dataclass
class And(BoolOp):
    def __init__(
        self, pp_type: b.PPType, values: Sequence[PhyExpression],
        target: regs.Register
    ):
        super().__init__(pp_type, values, target)

    def _initial(self) -> int:
        return 1

    def _op(self) -> str:
        return 'and'


@dataclass
class Or(BoolOp):
    def __init__(
        self, pp_type: b.PPType, values: Sequence[PhyExpression],
        target: regs.Register
    ):
        super().__init__(pp_type, values, target)

    def _initial(self) -> int:
        return 0

    def _op(self) -> str:
        return 'or'
