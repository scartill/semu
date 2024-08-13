from dataclasses import dataclass
from typing import Sequence, Callable
import logging as lg

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.pointers as ptrs


@dataclass
class BuiltinInlineImpl(el.Expression):
    def __init__(self, target_type: b.TargetType, target: regs.Register):
        super().__init__(target_type, target)

    def json(self):
        data = super().json()
        data.update({'Type': 'BuiltinInline'})
        return data


Factory = Callable[[b.TargetType, el.Expressions, regs.Register], BuiltinInlineImpl]


@dataclass
class BuiltinInline(n.KnownName, el.Expression):
    factory: Factory
    return_type: b.TargetType

    def __init__(
        self, namespace: n.INamespace, name: str, target_type: b.TargetType,
        factory: Factory
    ):
        n.KnownName.__init__(self, namespace, name, target_type)
        # Builtin functions have no address
        el.Expression.__init__(self, t.Callable, regs.VOID_REGISTER)
        self.factory = factory
        self.return_type = target_type


@dataclass
class Checkpoint(BuiltinInlineImpl):
    arg: int

    def emit(self) -> Sequence[str]:
        return [
            '// Checkpoint',
            f'%check {self.arg}'
        ]

    def json(self):
        data = super().json()
        data.update({'Checkpoint': self.arg})
        return data


@dataclass
class Assertion(BuiltinInlineImpl):
    source: el.Expression
    value: int

    def emit(self) -> Sequence[str]:
        return flatten([
            self.source.emit(),
            '// Assertion',
            f'%assert {self.source.target} {self.value}',
            '// Return null',
            f'ldc 0 {self.target}'
        ])

    def json(self):
        data = super().json()

        data.update({
            'Assert': self.value,
            'Source': self.source.json()
        })

        return data


@dataclass
class BoolToInt(BuiltinInlineImpl):
    source: el.Expression

    def emit(self) -> Sequence[str]:
        # Does nothing on the assembly level
        return self.source.emit()


class Deref32(BuiltinInlineImpl):
    source: el.Expression

    def __init__(self, source: el.Expression, target: regs.Register):
        assert isinstance(source.target_type, t.PointerType)
        super().__init__(source.target_type.ref_type, target)
        self.source = source

    def json(self):
        data = el.Expression.json(self)
        data.update({'DerefOf': self.target_type.json()})
        return data

    def emit(self) -> el.Sequence[str]:
        assert isinstance(self.target_type, t.PhysicalType)

        return flatten([
            f'// Pointer type: {self.target_type.name}',
            self.source.emit(),
            '// Dereference',
            f'mmr {self.source.target} {self.target}'
        ])


def create_checkpoint(
    target_type: b.TargetType, args: el.Expressions, target: regs.Register
):
    lg.debug('Checkpoint')

    if len(args) != 1:
        raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

    arg = args[0]

    if not isinstance(arg, el.ConstantExpression):
        raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

    # Inlining the checkpoint number
    value = arg.value
    return Checkpoint(target_type, target, value)


def create_assert(target_type: b.TargetType, args: el.Expressions, target: regs.Register):
    if len(args) != 2:
        raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

    source = args[0]
    value_expr = args[1]

    if not isinstance(value_expr, el.ConstantExpression):
        raise UserWarning(f"'assertion' expects a constant value, got {value_expr}")

    if source.target_type != t.Int32:
        raise UserWarning(
            f"'assertion' expects a int32 source, got {source.target_type}"
        )

    if value_expr.target_type != t.Int32:
        raise UserWarning(
            f"'assertion' expects a int32 value, got {value_expr.target_type}"
        )

    # Inlining the value
    value = value_expr.value
    return Assertion(target_type, target, source, value)


def create_bool2int(target_type: b.TargetType, args: el.Expressions, target: regs.Register):
    lg.debug('BoolToInt')

    if len(args) != 1:
        raise UserWarning(f"'bool_to_int' expects 1 argument, got {len(args)}")

    source = args[0]

    if source.target_type != t.Bool32:
        raise UserWarning(f"'bool_to_int' expects a bool32 source, got {source.target_type}")

    return BoolToInt(target_type, target, source)


def create_deref(target_type: b.TargetType, args: el.Expressions, target: regs.Register):
    lg.debug('Deref32')

    if len(args) != 1:
        raise UserWarning(f"'deref' expects 1 argument, got {len(args)}")

    source = args[0]

    if not isinstance(source.target_type, t.PointerType):
        raise UserWarning(f"'deref' expects a pointer source, got {source.target_type}")

    return Deref32(source, target)


def get(namespace: n.INamespace) -> Sequence[n.KnownName]:
    t.Unit.parent = namespace
    t.Int32.parent = namespace
    t.Bool32.parent = namespace
    ptrs.PointerOperatorType.parent = namespace

    return [
        t.Unit,
        t.Int32,
        t.Bool32,
        ptrs.PointerOperator,
        t.DecoratorType('staticmethod', namespace),
        BuiltinInline(namespace, 'checkpoint', t.Unit, create_checkpoint),
        BuiltinInline(namespace, 'assert_eq', t.Unit, create_assert),
        BuiltinInline(namespace, 'bool_to_int', t.Int32, create_bool2int),
        BuiltinInline(namespace, 'deref', t.AbstractPointer, create_deref)
    ]
