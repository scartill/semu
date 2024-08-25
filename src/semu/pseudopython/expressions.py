from typing import Sequence

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t


class Expression:
    pp_type: b.PPType

    def __init__(self, pp_type: b.PPType):
        super().__init__()
        self.pp_type = pp_type

    def json(self):
        return {
            'Class': 'Expression',
            'Type': self.pp_type.json()
        }


class PhyExpression(Expression, b.Element):
    target: regs.Register

    def __init__(self, pp_type: b.PPType, target: regs.Register):
        Expression.__init__(self, pp_type)
        b.Element.__init__(self)
        self.target = target

    def json(self):
        return {
            'Class': 'PhyExpression',
            'Target': self.target,
            'Expression': Expression.json(self),
            'Element': b.Element.json(self)
        }

    def __str__(self) -> str:
        eclass = self.__class__.__name__
        return f'expression<{eclass} -> reg:{self.target}>'


Expressions = Sequence[Expression]


class ConstantExpression(PhyExpression):
    value: int | bool

    def __init__(
        self, pp_type: b.PPType, value: int | bool,
        target: regs.Register
    ):
        super().__init__(pp_type, target)
        self.value = value

    def _convert_value(self) -> int:
        if self.pp_type == t.Int32:
            return self.value

        if self.pp_type == t.Bool32:
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


class GenericVariable(b.KnownName):
    def __init__(self, namespace: b.INamespace, name: str, pp_type: b.PPType):
        b.KnownName.__init__(self, namespace, name, pp_type)

    def json(self):
        data = super().json()
        data['Class'] = 'GenericVariable'
        return data


class GlobalVariable(b.Element, GenericVariable):
    def __init__(self, namespace: b.INamespace, name: str, pp_type: b.PPType):
        GenericVariable.__init__(self, namespace, name, pp_type)
        b.Element.__init__(self)

    def typelabel(self) -> str:
        return 'global'

    def json(self):
        data: b.JSON = {'Class': 'GlobalVariable'}
        data['KnownName'] = GenericVariable.json(self)
        data['Element'] = b.Element.json(self)
        return data

    def emit(self):
        label = self.address_label()

        return [
            f'// Begin variable {self.name} of type {self.pp_type}',
            f'{label}:',        # label
            'nop',              # placeholder
            '// End variable'
        ]


class StackVariable(GenericVariable):
    offset: int

    def __init__(
        self, namespace: b.INamespace, name: str, offset: int,
        pp_type: t.PhysicalType
    ):
        super().__init__(namespace, name, pp_type)
        self.offset = offset

    def json(self):
        data = super().json()
        data['Class'] = 'StackVariable'
        data['Offset'] = self.offset
        return data


class Assignable(PhyExpression):
    name: str | None
    pointer: PhyExpression

    def __init__(
        self, pointer: PhyExpression,
        target: regs.Register = regs.DEFAULT_REGISTER,
        name: str | None = None
    ):

        assert isinstance(pointer.pp_type, t.PointerType)
        super().__init__(pointer.pp_type, target)
        self.pointer = pointer
        self.name = name

    def valuetype(self) -> t.PhysicalType:
        assert isinstance(self.pp_type, t.PointerType)
        return self.pp_type.ref_type

    def __str__(self) -> str:
        return self.name if self.name else '<dynamic>'

    def json(self):
        data = super().json()
        data['Class'] = 'Assignable'
        return data

    def emit(self):
        return flatten([
            f'// Assignable {self} pass-through',
            self.pointer.emit(),
            f'mrr {self.pointer.target} {self.target}'
        ])


class Assignor(PhyExpression):
    assignable: Assignable
    source: PhyExpression

    def __init__(
        self, assignable: Assignable, source: PhyExpression,
        target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(assignable.pp_type, t.PointerType)
        pp_type = assignable.pp_type.ref_type
        super().__init__(pp_type, target)
        self.assignable = assignable
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Class': 'Assignor',
            'Target': self.assignable.json(),
            'Expression': self.source.json()
        })

        return data

    def emit(self) -> b.Sequence[str]:
        available = regs.get_available([
            self.assignable.target,
            self.source.target
        ])

        address = available.pop()
        value = available.pop()

        return flatten([
            '// Assignment begin',
            '// Calculating value begin',
            self.source.emit(),
            f'push {self.source.target}',
            '// Calculating value end',
            '// Calculating address',
            self.assignable.emit(),
            f'mrr {self.assignable.target} {address}',
            f'pop {value}',
            '// Calculating address end',
            '// Assign',
            f'mrm {value} {address}',
            '// End assignment'
        ])


class Retarget(PhyExpression):
    source: PhyExpression

    def __init__(self, source: PhyExpression, target: regs.Register):
        super().__init__(source.pp_type, target)
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
    def __init__(self, pp_type: b.PPType):
        super().__init__(pp_type)

    def json(self):
        data = super().json()
        data['Class'] = 'TypeWrapper'
        return data


# Built-in operator with no physical representation (e.g. type declaration)
class BuiltinMetaoperator(b.KnownName, Expression):
    def __init__(self, name: str):
        b.KnownName.__init__(self, None, name, b.Builtin)
        Expression.__init__(self, b.Builtin)

    def json(self):
        data = b.KnownName.json(self)
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


class ICompoundType:
    def load_member(
        self, parent_load: PhyExpression, name: str, target: regs.Register
    ) -> PhyExpression:

        raise NotImplementedError()


class ISequenceType:
    def load_item(self, parent_load: PhyExpression, index: int) -> PhyExpression:
        raise NotImplementedError()
