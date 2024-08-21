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
        return {'Class': 'Element'}


Elements = Sequence[Element]


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']

    def json(self):
        data = Element.json(self)
        data['Class'] = 'VoidElement'
        data['Void'] = self.comment
        return data


@dataclass
class Expression:
    target_type: b.TargetType

    def __init__(self, target_type: b.TargetType):
        super().__init__()
        self.target_type = target_type

    def json(self):
        return {
            'Class': 'Expression',
            'Type': self.target_type.json()
        }


class PhyExpression(Expression, Element):
    target: regs.Register

    def __init__(self, target_type: b.TargetType, target: regs.Register):
        Expression.__init__(self, target_type)
        Element.__init__(self)
        self.target = target

    def json(self):
        return {
            'Class': 'PhyExpression',
            'Target': self.target,
            'Expression': Expression.json(self),
            'Element': Element.json(self)
        }


Expressions = Sequence[Expression]


@dataclass
class ConstantExpression(PhyExpression):
    value: int | bool

    def __init__(
        self, target_type: b.TargetType, value: int | bool,
        target: regs.Register
    ):
        super().__init__(target_type, target)
        self.value = value

    def _convert_value(self) -> int:
        if self.target_type == t.Int32:
            return self.value

        if self.target_type == t.Bool32:
            return 1 if self.value else 0

        raise NotImplementedError()

    def json(self):
        data = super().json()
        data['Class'] = 'ConstantExpression'
        data['Constant'] = self.value
        return data

    def emit(self):
        value = self._convert_value()
        return f'ldc {value} {self.target}'


type PhyExpressions = Sequence[PhyExpression]


class GlobalVariable(Element, n.KnownName):
    def __init__(self, namespace: n.INamespace, name: str, target_type: b.TargetType):
        n.KnownName.__init__(self, namespace, name, target_type)
        Element.__init__(self)

    def typelabel(self) -> str:
        return 'global'

    def json(self):
        data: b.JSON = {'Class': 'GlobalVariable'}
        data['KnownName'] = n.KnownName.json(self)
        data['Element'] = Element.json(self)
        return data

    def emit(self):
        label = self.address_label()

        return [
            f'// Begin variable {self.name} of type {self.target_type}',
            f'{label}:',        # label
            'nop',              # placeholder
            '// End variable'
        ]


@dataclass
class Assignor(Element):
    target: n.KnownName
    source: PhyExpression

    def json(self):
        data = super().json()

        data.update({
            'Class': 'Assignor',
            'Target': self.target.name,
            'Expression': self.source.json()
        })

        return data


@dataclass
class GlobalVariableAssignment(Assignor):
    def json(self):
        data = super().json()

        data.update({
            'Class': 'GlobalVariableAssignment',
        })

        return data

    def emit(self):
        temp = regs.get_temp([self.source.target])
        label = self.target.address_label()

        return flatten([
            f"// Calculating var:{self.target.name} into reg:{self.source.target}",
            self.source.emit(),
            f'// Storing var:{self.target.name}',
            f'ldr &{label} {temp}',
            f'mrm {self.source.target} {temp}',
        ])


class GlobalVariableLoad(PhyExpression):
    variable: GlobalVariable

    def __init__(self, variable: GlobalVariable, target: regs.Register):
        super().__init__(variable.target_type, target)
        self.variable = variable

    def json(self):
        data = super().json()
        data['Class'] = 'GlobalVariableLoad'
        data['Variable'] = self.variable.name
        return data

    def emit(self):
        temp = regs.get_temp([self.target])
        label = self.variable.address_label()

        return flatten([
            f'// Loading var:{self.variable.name} address',
            f'ldr &{label} {temp}',
            f'// Setting var:{self.variable.name} to reg:{self.target}',
            f'mmr {temp} {self.target}',
        ])


class DecoratorApplication(Expression):
    decorator: t.DecoratorType

    def json(self):
        return {'ApplyDecorator': self.decorator.name}

    def __init__(self, decorator: t.DecoratorType):
        super().__init__(t.Unit)
        self.decorator = decorator

    def name(self) -> str:
        return self.decorator.name


type DecoratorApplications = Sequence[DecoratorApplication]


class TypeWrapper(Expression):
    def __init__(self, target_type: b.TargetType):
        super().__init__(target_type)

    def json(self):
        data = super().json()
        data['Class'] = 'TypeWrapper'
        return data


# Built-in operator with no physical representation (e.g. type declaration)
class BuiltinMetaoperator(n.KnownName, Expression):
    def __init__(self, name: str):
        n.KnownName.__init__(self, None, name, b.Builtin)
        Expression.__init__(self, b.Builtin)

    def json(self):
        data = n.KnownName.json(self)
        data.update({'Class': 'Metaoperator', 'Name': self.name})
        return data


class MetaList(Expression):
    elements: Expressions

    def __init__(self, elements: Expressions):
        super().__init__(t.Unit)
        self.elements = elements

    def json(self):
        return {
            'Class': 'MetaList',
            'Elements': [e.json() for e in self.elements]
        }
