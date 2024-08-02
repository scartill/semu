from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, Element


@dataclass
class If(Element):
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
        true_label = self._make_label('true')
        false_label = self._make_label('false')
        end_label = self._make_label('end')

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


@dataclass
class While(Element):
    test: Expression
    body: Sequence[Element]

    def __init__(self, test: Expression, body: Sequence[Element]):
        super().__init__()
        self.test = test
        self.body = body

    def emit(self) -> Sequence[str]:
        start_label = self._make_label('start')
        body_label = self._make_label('body')
        end_label = self._make_label('end')

        temp = self._get_temp([self.test.target])

        return flatten([
            '// while block',
            f'{start_label}:',
            f'push {temp}',
            self.test.emit(),
            f'ldr &{body_label} {temp}',
            f'jgt {self.test.target} {temp}',
            f'ldr &{end_label} {temp}',
            f'jmp {temp}',
            f'{body_label}:',
            [statement.emit() for statement in self.body],
            f'ldr &{start_label} {temp}',
            f'jmp {temp}',
            f'{end_label}:',
            f'pop {temp}',
            '// end while block',
        ])
