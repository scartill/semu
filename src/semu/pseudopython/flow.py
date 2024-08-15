from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs


@dataclass
class If(el.Element):
    test: el.PhysicalExpression
    true_body: el.Elements
    false_body: el.Elements

    def json(self):
        data = super().json()

        data.update({
            'Test': self.test.json(),
            'TrueBody': [e.json() for e in self.true_body],
            'FalseBody': [e.json() for e in self.false_body]
        })

        return data

    def __init__(
        self, test: el.PhysicalExpression,
        true_body: el.Elements, false_body: el.Elements
    ):
        super().__init__()
        self.test = test
        self.true_body = true_body
        self.false_body = false_body

    def emit(self) -> Sequence[str]:
        true_label = self._make_label('true')
        false_label = self._make_label('false')
        end_label = self._make_label('end')
        temp = regs.get_temp([self.test.target])

        return flatten([
            '// if block',
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
            '// end if block'
        ])


@dataclass
class While(el.Element):
    test: el.PhysicalExpression
    body: el.Elements

    def __init__(self, test: el.PhysicalExpression, body: el.Elements):
        super().__init__()
        self.test = test
        self.body = body

    def json(self):
        data = super().json()

        data.update({
            'Test': self.test.json(),
            'Body': [e.json() for e in self.body]
        })

        return data

    def emit(self) -> Sequence[str]:
        start_label = self._make_label('start')
        body_label = self._make_label('body')
        end_label = self._make_label('end')
        temp = regs.get_temp([self.test.target])

        return flatten([
            '// while block',
            f'{start_label}:',
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
            '// end while block'
        ])
