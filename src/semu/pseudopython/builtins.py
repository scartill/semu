from dataclasses import dataclass
from typing import Sequence, Type
import logging as lg

from semu.pseudopython.flatten import flatten

from semu.pseudopython.elements import (
    Expression, Register, ConstantExpression, KnownName, TargetType
)


@dataclass
class BuiltinImplementation(Expression):
    def __init__(self, known_name: KnownName, args: Sequence[Expression], target: Register):
        super().__init__(known_name.target_type, target)


@dataclass
class BuiltinFunction(KnownName):
    func: Type[BuiltinImplementation]

    def __init__(self, name: str, target_type: TargetType, func: Type):
        super().__init__(name, target_type)
        self.func = func


@dataclass
class Checkpoint(BuiltinImplementation):
    arg: int

    def __init__(self, known_name: KnownName, args: Sequence[Expression], target: Register):
        super().__init__(known_name, args, target)

        lg.debug(f'Checkpoint {args}')

        if len(args) != 1:
            raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

        arg = args[0]

        if not isinstance(arg, ConstantExpression):
            raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

        # Inlining the checkpoint number
        self.arg = arg.value

    def emit(self) -> Sequence[str]:
        return [
            '// Checkpoint',
            f'.check {self.arg}'
        ]


@dataclass
class Assertion(BuiltinImplementation):
    source: Expression
    value: int

    def __init__(self, known_name: KnownName, args: Sequence[Expression], target: Register):
        super().__init__(known_name, args, target)

        lg.debug(f'Assertion {args}')

        if len(args) != 2:
            raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

        self.source = args[0]
        value_expr = args[1]

        if not isinstance(value_expr, ConstantExpression):
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
            self.source.emit(),
            f'.assert {self.source.target} {self.value}'
        ])


@dataclass
class BoolToInt(BuiltinImplementation):
    source: Expression

    def __init__(self, known_name: KnownName, args: Sequence[Expression], target: Register):
        super().__init__(known_name, args, target)

        # TODO: More structurally correct would be have these in helpers
        lg.debug(f'BoolToInt {args}')

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


def get() -> Sequence[BuiltinFunction]:
    return [
        BuiltinFunction('checkpoint', 'unit', Checkpoint),
        BuiltinFunction('assert_eq', 'unit', Assertion),
        BuiltinFunction('bool_to_int', 'int32', BoolToInt)
    ]
