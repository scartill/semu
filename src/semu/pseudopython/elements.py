from typing import Literal, Sequence, Any, Set
from dataclasses import dataclass
from random import randint

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs


TargetType = Literal['unit', 'int32', 'bool32', 'callable']


class KnownName:
    name: str
    target_type: TargetType

    def __init__(self, name: str, target_type: TargetType):
        self.name = name
        self.target_type = target_type

    def __str__(self) -> str:
        return f'{self.name}: {self.target_type}'

    def label_name(self) -> str:
        raise NotImplementedError()


class Constant(KnownName):
    value: Any

    def __init__(self, name: str, target_type: TargetType, value: Any):
        super().__init__(name, target_type)
        self.value = value

    def __str__(self) -> str:
        return f'{self.name}: {self.target_type} = {self.value}'


class GlobalVar(KnownName):
    def __init__(self, name: str, target_type: TargetType):
        super().__init__(name, target_type)

    def label_name(self) -> str:
        return f'_global_{self.name}'


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


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']


@dataclass
class Expression(Element):
    target_type: TargetType
    target: regs.Register

    def __init__(self, target_type: TargetType, target: regs.Register):
        super().__init__()
        self.target_type = target_type
        self.target = target


Expressions = Sequence[Expression]


@dataclass
class GlobalVariableCreate(Element, GlobalVar):
    def __init__(self, name: str, target_type: TargetType):
        KnownName.__init__(self, name, target_type)
        Element.__init__(self)

    def label_name(self) -> str:
        return f'_global_variable_{self.name}'

    def emit(self):
        label = self.label_name()

        return [
            f'// Begin variable {self.name}',
            f'{label}:',        # label
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
    source: regs.Register = regs.DEFAULT_REGISTER

    def emit(self):
        temp = regs.get_temp([self.source])
        label = self.target.label_name()

        return flatten([
            f'// Saving reg:{temp}',
            f'push {temp}',
            f"// Calculating var:{self.target.name} into reg:{self.source}",
            self.expr.emit(),
            f'// Storing var:{self.target.name}',
            f'ldr &{label} {temp}',
            f'mrm {self.source} {temp}',
            f'// Restoring reg:{temp}',
            f'pop {temp}'
        ])


@dataclass
class GlobalVariableLoad(Expression):
    name: KnownName

    def __init__(self, name: KnownName, target: regs.Register):
        super().__init__(name.target_type, target)
        self.name = name

    def emit(self):
        temp = regs.get_temp([self.target])
        label = self.name.label_name()

        return flatten([
            f'// Saving reg:{temp}',
            f'push {temp}',
            f'// Loading var:{self.name} address',
            f'ldr &{label} {temp}',
            f'// Setting var:{self.name} to reg:{self.target}',
            f'mmr {temp} {self.target}',
            f'// Restoring reg:{temp}',
            f'pop {temp}'
        ])
