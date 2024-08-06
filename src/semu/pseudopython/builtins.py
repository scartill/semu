from dataclasses import dataclass
from typing import Sequence, Type
import logging as lg

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.elements as el


@dataclass
class BuiltinInlineImpl(el.Expression):
    def __init__(
            self, target_type: el.TargetType, args: el.Expressions, target: regs.Register
    ):
        super().__init__(target_type, target)


@dataclass
class BuiltinInline(el.Callable, el.Expression):
    func: Type[BuiltinInlineImpl]
    return_type: el.TargetType

    def __init__(self, name: str, target_type: el.TargetType, func: Type):
        el.Callable.__init__(self, name, target_type)
        # Builtin functions have no address
        el.Expression.__init__(self, 'callable', regs.VOID_REGISTER)
        self.func = func
        self.return_type = target_type


@dataclass
class Checkpoint(BuiltinInlineImpl):
    arg: int

    def __init__(
            self, target_type: el.TargetType, args: el.Expressions, target: regs.Register
    ):
        super().__init__(target_type, args, target)
        lg.debug('Checkpoint')

        if len(args) != 1:
            raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

        arg = args[0]

        if not isinstance(arg, el.ConstantExpression):
            raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

        # Inlining the checkpoint number
        self.arg = arg.value

    def emit(self) -> Sequence[str]:
        return [
            '// Checkpoint',
            f'.check {self.arg}'
        ]


@dataclass
class Assertion(BuiltinInlineImpl):
    source: el.Expression
    value: int

    def __init__(self, target_type: el.TargetType, args: el.Expressions, target: regs.Register):
        super().__init__(target_type, args, target)
        lg.debug('Assertion')

        if len(args) != 2:
            raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

        self.source = args[0]
        value_expr = args[1]

        if not isinstance(value_expr, el.ConstantExpression):
            raise UserWarning(f"'assertion' expects a constant value, got {value_expr}")

        if self.source.target_type != 'int32':
            raise UserWarning(
                f"'assertion' expects a int32 source, got {self.source.target_type}"
            )

        if value_expr.target_type != 'int32':
            raise UserWarning(
                f"'assertion' expects a int32 value, got {value_expr.target_type}"
            )

        # Inlining the value
        self.value = value_expr.value

    def emit(self) -> Sequence[str]:
        return flatten([
            '// Assertion',
            f'pop {self.target}',
            f'.assert {self.source.target} {self.value}',
            '// Return null',
            f'ldc 0 {self.target}',
            f'push {self.target}'
        ])


@dataclass
class BoolToInt(BuiltinInlineImpl):
    source: el.Expression

    def __init__(self, target_type: el.TargetType, args: el.Expressions, target: regs.Register):
        super().__init__(target_type, args, target)

        # TODO: move these constructors to factory functions
        lg.debug('BoolToInt')

        if len(args) != 1:
            raise UserWarning(f"'bool_to_int' expects 1 argument, got {len(args)}")

        self.source = args[0]

        if self.source.target_type != 'bool32':
            raise UserWarning(
                f"'bool_to_int' expects a bool32 source, got {self.source.target_type}"
            )

    def emit(self) -> Sequence[str]:
        # Does nothing on the assembly level
        return self.source.emit()


def get() -> Sequence[BuiltinInline]:
    return [
        BuiltinInline('checkpoint', 'unit', Checkpoint),
        BuiltinInline('assert_eq', 'unit', Assertion),
        BuiltinInline('bool_to_int', 'int32', BoolToInt)
    ]
