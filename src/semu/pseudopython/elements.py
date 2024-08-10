from typing import Literal, Sequence, Any, Set, Dict
from dataclasses import dataclass
from random import randint

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs

JSON = Dict[str, Any]
TargetType = Literal['unit', 'int32', 'bool32', 'callable']
TargetTypes = Sequence[TargetType]


class KnownName:
    name: str
    target_type: TargetType

    def __init__(self, name: str, target_type: TargetType):
        self.name = name
        self.target_type = target_type

    def json(self) -> JSON:
        return {'Name': self.name, 'Type': self.target_type}

    def address_label(self) -> str:
        raise NotImplementedError()


class Constant(KnownName):
    value: Any

    def __init__(self, name: str, target_type: TargetType, value: Any):
        super().__init__(name, target_type)
        self.value = value

    def json(self) -> JSON:
        data = super().json()
        data.update({'Value': self.value})
        return data


class GlobalVar(KnownName):
    def __init__(self, name: str, target_type: TargetType):
        super().__init__(name, target_type)

    def address_label(self) -> str:
        return f'_global_{self.name}'

    def json(self) -> JSON:
        data = super().json()
        data.update({'Variable': 'global'})
        return data


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

    def json(self) -> JSON:
        return {}


Elements = Sequence[Element]


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']

    def json(self) -> JSON:
        data = Element.json(self)
        data.update({'void': self.comment})
        return data


@dataclass
class Expression(Element):
    target_type: TargetType
    target: regs.Register

    def __init__(self, target_type: TargetType, target: regs.Register):
        super().__init__()
        self.target_type = target_type
        self.target = target

    def json(self) -> JSON:
        data = Element.json(self)
        data.update({'Type': self.target_type, 'Target': self.target})
        return data


Expressions = Sequence[Expression]


@dataclass
class GlobalVariableCreate(Element, GlobalVar):
    def __init__(self, name: str, target_type: TargetType):
        KnownName.__init__(self, name, target_type)
        Element.__init__(self)

    def address_label(self) -> str:
        return f'_global_variable_{self.name}'

    def emit(self):
        label = self.address_label()

        return [
            f'// Begin variable {self.name}',
            f'{label}:',        # label
            'nop',              # placeholder
            '// End variable'
        ]

    def json(self) -> JSON:
        data = {'Create': 'global'}
        data_kn = KnownName.json(self)
        data_el = Element.json(self)
        data.update(data_kn)
        data.update(data_el)
        return data_kn


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
class GlobalVarAssignment(Element):
    target: KnownName
    expr: Expression

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

    def json(self) -> JSON:
        data = Element.json(self)

        data.update({
            'GlobalAssign': self.target.json(),
            'Expression': self.expr.json()
        })

        return data


@dataclass
class GlobalVariableLoad(Expression):
    name: KnownName

    def __init__(self, name: KnownName, target: regs.Register):
        super().__init__(name.target_type, target)
        self.name = name

    def json(self) -> JSON:
        data = super().json()
        data.update({'GlobalLoad': self.name.json()})
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
