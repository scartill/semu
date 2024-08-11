from dataclasses import dataclass
from typing import Sequence, Callable
import logging as lg

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.names as n
import semu.pseudopython.elements as el


@dataclass
class BuiltinInlineImpl(el.Expression):
    def __init__(
            self, target_type: n.TargetType, args: el.Expressions, target: regs.Register
    ):
        super().__init__(target_type, target)

    def json(self):
        data = super().json()
        data.update({'Type': 'BuiltinInline'})
        return data


Factory = Callable[[n.TargetType, el.Expressions, regs.Register], BuiltinInlineImpl]


@dataclass
class BuiltinInline(n.KnownName, el.Expression):
    factory: Factory
    return_type: n.TargetType

    def __init__(
        self, namespace: n.INamespace, name: str, target_type: n.TargetType,
        factory: Factory
    ):
        n.KnownName.__init__(self, namespace, name, target_type)
        # Builtin functions have no address
        el.Expression.__init__(self, 'callable', regs.VOID_REGISTER)
        self.factory = factory
        self.return_type = target_type


@dataclass
class Checkpoint(BuiltinInlineImpl):
    arg: int

    def emit(self) -> Sequence[str]:
        return [
            '// Checkpoint',
            f'.check {self.arg}'
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
            '// Assertion',
            '// Ignore the second param',
            f'pop {self.target}',
            '// Take the first param',
            f'pop {self.target}',
            f'.assert {self.source.target} {self.value}',
            '// Restoring the stack',
            f'push {self.target}',
            f'push {self.target}'
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


def create_checkpoint(
    target_type: n.TargetType, args: el.Expressions, target: regs.Register
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


@dataclass
class BoolToInt(BuiltinInlineImpl):
    source: el.Expression

    def emit(self) -> Sequence[str]:
        # Does nothing on the assembly level
        return self.source.emit()


def create_assert(target_type: n.TargetType, args: el.Expressions, target: regs.Register):
    if len(args) != 2:
        raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

    source = args[0]
    value_expr = args[1]

    if not isinstance(value_expr, el.ConstantExpression):
        raise UserWarning(f"'assertion' expects a constant value, got {value_expr}")

    if source.target_type != 'int32':
        raise UserWarning(
            f"'assertion' expects a int32 source, got {source.target_type}"
        )

    if value_expr.target_type != 'int32':
        raise UserWarning(
            f"'assertion' expects a int32 value, got {value_expr.target_type}"
        )

    # Inlining the value
    value = value_expr.value
    return Assertion(target_type, target, source, value)


def create_bool2int(target_type: n.TargetType, args: el.Expressions, target: regs.Register):
    lg.debug('BoolToInt')

    if len(args) != 1:
        raise UserWarning(f"'bool_to_int' expects 1 argument, got {len(args)}")

    source = args[0]

    if source.target_type != 'bool32':
        raise UserWarning(f"'bool_to_int' expects a bool32 source, got {source.target_type}")

    return BoolToInt(target_type, target, source)


def get(namespace: n.INamespace) -> Sequence[BuiltinInline]:
    return [
        BuiltinInline(namespace, 'checkpoint', 'unit', create_checkpoint),
        BuiltinInline(namespace, 'assert_eq', 'unit', create_assert),
        BuiltinInline(namespace, 'bool_to_int', 'int32', create_bool2int)
    ]
