from dataclasses import dataclass
from typing import Sequence
import logging as lg

from semu.pseudopython.flatten import flatten
from semu.pseudopython.elements import Expression, Register, ConstantExpression


@dataclass
class Checkpoint(Expression):
    arg: int

    def __init__(self, args: Sequence[Expression], target: Register):
        lg.debug(f'Checkpoint {args}')

        if len(args) != 1:
            raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

        arg = args[0]

        if not isinstance(arg, ConstantExpression):
            raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

        self.target_type = 'unit'
        self.target = target  # Checkpoints don't have a actual target

        # Inlining the checkpoint number
        self.arg = arg.value

    def emit(self) -> Sequence[str]:
        return [
            '// Checkpoint',
            f'.check {self.arg}'
        ]


@dataclass
class Assertion(Expression):
    source: Expression
    value: int

    def __init__(self, args: Sequence[Expression], target: Register):
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

        self.target_type = 'unit'
        self.target = target  # Assertions don't have an actual target

        # Inlining the value
        self.value = value_expr.value

    def emit(self) -> Sequence[str]:
        return flatten([
            '// Assertion',
            self.source.emit(),
            f'.assert {self.source.target} {self.value}'
        ])


@dataclass
class BoolToInt(Expression):
    source: Expression

    def __init__(self, args: Sequence[Expression], target: Register):
        # TODO: More structurally correct would be have these in helpers
        lg.debug(f'BoolToInt {args}')

        self.target_type = 'int32'
        self.target = target

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
