from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression


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
