from typing import Literal, Sequence, Any, List, Set
from dataclasses import dataclass
from random import randint

from semu.pseudopython.flatten import flatten


Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
TargetType = Literal['unit', 'int32', 'bool32']


REGISTERS: List[Register] = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)
DEFAULT_REGISTER = 'a'


@dataclass
class KnownName:
    name: str
    target_type: TargetType

    def __str__(self) -> str:
        return f'{self.name}: {self.target_type}'


@dataclass
class Constant(KnownName):
    value: Any


@dataclass
class GlobalVar(KnownName):
    pass


@dataclass
class LocalVar(KnownName):
    pass


class Element:
    labels: Set[str]

    def __init__(self):
        self.labels = set()

    def _make_label(self, description) -> str:
        label = f'_label_{description}_{randint(1_000_000, 9_000_000)}'

        if label in self.labels:
            return self._make_label(description)
        else:
            self.labels.add(label)
            return label

    def emit(self) -> Sequence[str]:
        raise NotImplementedError()

    def _get_available_registers(self, used: List[Register]) -> Set[Register]:
        available = set(REGISTERS.copy())
        available.difference_update(used)
        return available

    def _get_temp(self, used: List[Register]) -> Register:
        available = self._get_available_registers(used)
        temp = available.pop()
        return temp


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']


@dataclass
class Expression(Element):
    target_type: TargetType
    target: Register

    def __init__(self, target_type: TargetType, target: Register):
        super().__init__()
        self.target_type = target_type
        self.target = target


@dataclass
class GlobalVariableCreate(Element):
    name: str

    def emit(self):
        return [
            f'// Begin variable {self.name}',
            f'{self.name}:',        # label
            'nop',                  # placeholder
            '// End variable',
        ]


@dataclass
class ConstantExpression(Expression):
    value: int | bool

    def _convert_value(self) -> int:
        if self.target_type == 'int32':
            return self.value

        if self.target_type == 'bool32':
            return 1 if self.value else 0

        raise NotImplementedError()

    def emit(self):
        value = self._convert_value()
        return f'ldc {value} {self.target}'


@dataclass
class GlobalVarAssignment(Element):
    target: KnownName
    expr: Expression
    source: Register = DEFAULT_REGISTER

    def emit(self):
        temp = self._get_temp([self.source])

        return flatten([
            f'// Saving reg:{temp}',
            f'push {temp}',
            f"// Calculating var:{self.target.name} into reg:{self.source}",
            self.expr.emit(),
            f'// Storing var:{self.target.name}',
            f'ldr &{self.target.name} {temp}',
            f'mrm {self.source} {temp}',
            f'// Restoring reg:{temp}',
            f'pop {temp}'
        ])


@dataclass
class GlobalVariableLoad(Expression):
    name: str

    def emit(self):
        temp = self._get_temp([self.target])

        return flatten([
            f'// Saving reg:{temp}',
            f'push {temp}',
            f'// Loading var:{self.name} address',
            f'ldr &{self.name} {temp}',
            f'// Setting var:{self.name} to reg:{self.target}',
            f'mmr {temp} {self.target}',
            f'// Restoring reg:{temp}',
            f'pop {temp}'
        ])
