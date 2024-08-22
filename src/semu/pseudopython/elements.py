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

    def __str__(self) -> str:
        eclass = self.__class__.__name__
        return f'expression<{eclass} -> reg:{self.target}>'


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


class StackVariable(n.KnownName):
    offset: int

    def __init__(
        self, namespace: n.INamespace, name: str, offset: int,
        target_type: t.PhysicalType
    ):
        n.KnownName.__init__(self, namespace, name, target_type)
        self.offset = offset

    def json(self):
        data = super().json()
        data['Class'] = 'StackVariable'
        data['Offset'] = self.offset
        return data


class Assignor(PhyExpression):
    target_load: PhyExpression
    source: PhyExpression

    def __init__(
        self, target_load: PhyExpression, source: PhyExpression,
        target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(target_load.target_type, t.PointerType)
        target_type = target_load.target_type.ref_type
        super().__init__(target_type, target)
        self.target_load = target_load
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Class': 'Assignor',
            'Target': self.target_load.json(),
            'Expression': self.source.json()
        })

        return data

    def emit(self) -> b.Sequence[str]:
        available = regs.get_available([
            self.target_load.target,
            self.source.target
        ])

        address = available.pop()
        value = available.pop()

        return flatten([
            f'// Assigning from reg:{self.source.target}',
            '// Calculating value',
            self.source.emit(),
            f'push {self.source.target}',
            '// Calculating address',
            self.target_load.emit(),
            f'mrr {self.target_load.target} {address}',
            f'pop {value}',
            '// Assign',
            f'mrm {value} {address}',
            '// End assignment'
        ])


class ValueLoader(PhyExpression):
    source: PhyExpression

    def __init__(self, source: PhyExpression, target: regs.Register):
        assert isinstance(source.target_type, t.PointerType)
        super().__init__(source.target_type.ref_type, target)
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Class': 'Assignor',
            'Target': self.target,
            'Expression': self.source.json()
        })

        return data

    def emit(self):
        available = regs.get_available([
            self.source.target,
            self.target
        ])

        address = available.pop()

        return flatten([
            f'// Loading value from reg:{self.source.target} to reg:{self.target}',
            '// Calculating address',
            self.source.emit(),
            f'mrr {self.source.target} {address}',
            '// Load value',
            f'mmr {address} {self.target}',
            '// End value load'
        ])


class Retarget(PhyExpression):
    source: PhyExpression

    def __init__(self, source: PhyExpression, target: regs.Register):
        super().__init__(source.target_type, target)
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Class': 'Retarget',
            'Expression': self.source.json()
        })

        return data

    def emit(self):
        return [
            f'// Retargeting from reg:{self.source.target} to reg:{self.target}',
            self.source.emit(),
            f'mrr {self.source.target} {self.target}'
        ]


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
