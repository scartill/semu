from dataclasses import dataclass
from typing import Sequence, Set
from random import randint

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, Element


@dataclass
class Flow(Element):
    labels: Set[str]

    def __init__(self):
        self.labels = set()

    def _make_label(self) -> str:
        label = f'__label_{randint(1_000_000, 9_000_000)}'

        if label in self.labels:
            return self._make_label()
        else:
            self.labels.add(label)
            return label


@dataclass
class If(Flow):
    test: Expression
    true_body: Sequence[Element]
    false_body: Sequence[Element]

    def __init__(
            self, test: Expression, 
            true_body: Sequence[Element], 
            false_body: Sequence[Element]
    ):
        super().__init__()
        self.test = test
        self.true_body = true_body
        self.false_body = false_body

    def emit(self) -> Sequence[str]:
        true_label = self._make_label()
        false_label = self._make_label()
        end_label = self._make_label()

        temp = self._get_temp([self.test.target])

        return flatten([
            '// if block',
            f'push {temp}',
            self.test.emit(),
            f'ldr &{true_label} {temp}',
            f'jgt {self.test.target} {temp}',
            '// false block',
            f'{false_label}:',
            [statement.emit() for statement in self.false_body],
            f'ldr &{end_label} {temp}',
            f'jmp {temp}',
            '// true block',
            f'{true_label}:',
            [statement.emit() for statement in self.true_body],
            f'{end_label}:',
            f'pop {temp}',
            '// end if block',
        ])
