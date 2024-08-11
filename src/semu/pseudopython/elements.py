from typing import Sequence, Set
from dataclasses import dataclass
from random import randint

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.names as names


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

    def json(self) -> names.JSON:
        return {}


Elements = Sequence[Element]


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']

    def json(self) -> names.JSON:
        data = Element.json(self)
        data.update({'void': self.comment})
        return data


@dataclass
class Expression(Element):
    target_type: names.TargetType
    target: regs.Register

    def __init__(self, target_type: names.TargetType, target: regs.Register):
        super().__init__()
        self.target_type = target_type
        self.target = target

    def json(self):
        data = Element.json(self)
        data.update({'Type': self.target_type, 'Target': self.target})
        return data


Expressions = Sequence[Expression]


@dataclass
class GlobalVariableCreate(Element, names.GlobalVariable):
    def __init__(self, namespace: names.INamespace, name: str, target_type: names.TargetType):
        names.KnownName.__init__(self, namespace, name, target_type)
        Element.__init__(self)

    def typelabel(self) -> str:
        return 'global'

    def json(self):
        data = {'Create': 'global'}
        data_kn = names.KnownName.json(self)
        data_el = Element.json(self)
        data.update(data_kn)
        data.update(data_el)
        return data_kn

    def emit(self):
        label = self.address_label()

        return [
            f'// Begin variable {self.name}',
            f'{label}:',        # label
            'nop',              # placeholder
            '// End variable'
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

    def json(self):
        data = super().json()
        data.update({'Constant': self.value})
        return data


@dataclass
class GlobalVariableAssignment(Element):
    target: names.KnownName
    expr: Expression

    def json(self):
        data = Element.json(self)

        data.update({
            'GlobalAssign': self.target.json(),
            'Expression': self.expr.json()
        })

        return data

    def emit(self):
        temp = regs.get_temp([self.expr.target])
        label = self.target.address_label()

        return flatten([
            f"// Calculating var:{self.target.name} into reg:{self.expr.target}",
            self.expr.emit(),
            f'// Storing var:{self.target.name}',
            f'ldr &{label} {temp}',
            f'mrm {self.expr.target} {temp}',
        ])


@dataclass
class GlobalVariableLoad(Expression):
    name: names.KnownName

    def __init__(self, name: names.KnownName, target: regs.Register):
        super().__init__(name.target_type, target)
        self.name = name

    def json(self):
        data = super().json()
        data.update({'GlobalLoad': self.name.name})
        return data

    def emit(self):
        temp = regs.get_temp([self.target])
        label = self.name.address_label()

        return flatten([
            f'// Loading var:{self.name} address',
            f'ldr &{label} {temp}',
            f'// Setting var:{self.name} to reg:{self.target}',
            f'mmr {temp} {self.target}',
        ])
