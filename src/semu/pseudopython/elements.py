from typing import Sequence, Set
from dataclasses import dataclass
from random import randint

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n


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

    def json(self) -> b.JSON:
        return {}


Elements = Sequence[Element]


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']

    def json(self):
        data = Element.json(self)
        data.update({'void': self.comment})
        return data


@dataclass
class Expression(Element):
    target_type: b.TargetType
    target: regs.Register

    def __init__(self, target_type: b.TargetType, target: regs.Register):
        super().__init__()
        self.target_type = target_type
        self.target = target

    def json(self):
        data = Element.json(self)
        data.update({'Type': self.target_type.json(), 'Target': self.target})
        return data


Expressions = Sequence[Expression]


@dataclass
class ConstantExpression(Expression):
    value: int | bool

    def _convert_value(self) -> int:
        if self.target_type == t.Int32:
            return self.value

        if self.target_type == t.Bool32:
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
class GlobalVariableCreate(Element, n.GlobalVariable):
    def __init__(self, namespace: n.INamespace, name: str, target_type: b.TargetType):
        n.KnownName.__init__(self, namespace, name, target_type)
        Element.__init__(self)

    def typelabel(self) -> str:
        return 'global'

    def json(self):
        data = {'Create': 'global'}
        data_kn = n.KnownName.json(self)
        data_el = Element.json(self)
        data.update(data_kn)
        data.update(data_el)
        return data_kn

    def emit(self):
        label = self.address_label()
        assert isinstance(self.target_type, t.PhysicalType)
        words = self.target_type.words

        return [
            f'// Begin variable {self.name} (size {words} words)',
            f'{label}:',        # label
            ['nop' for _ in range(words)],              # placeholder
            '// End variable'
        ]


@dataclass
class GlobalVariableAssignment(Element):
    target: n.KnownName
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


class GlobalVariableLoad(Expression):
    name: n.KnownName

    def __init__(self, name: n.KnownName, target: regs.Register):
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


class DecoratorApplication(Expression):
    decorator: t.DecoratorType

    def json(self):
        return {'ApplyDecorator': self.decorator.name}

    def __init__(self, decorator: t.DecoratorType, target: regs.Register):
        super().__init__(t.Unit, target)
        self.decorator = decorator

    def name(self) -> str:
        return self.decorator.name


type DecoratorApplications = Sequence[DecoratorApplication]


class TypeWrapper(Expression):
    def __init__(self, target_type: b.TargetType):
        super().__init__(target_type, regs.VOID_REGISTER)

    def json(self):
        tt = self.target_type
        descr = tt.name if isinstance(tt, t.NamedType) else tt.json()
        return {'TypeWrapper': descr}
