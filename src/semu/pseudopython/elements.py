import logging as lg
from typing import Literal, Sequence, Any
from dataclasses import dataclass

from semu.pseudopython.flatten import flatten


Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] | None
TargetType = Literal['unit', 'uint32']


REGISTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)
DEFAULT_REGISTER = 'a'


@dataclass
class KnownName:
    name: str
    target_type: TargetType

    def __str__(self) -> str:
        return f'{self.name}: {self.target_type}'


@dataclass
class Constant(KnownName):
    value: Any


@dataclass
class GlobalVar(KnownName):
    pass


@dataclass
class LocalVar(KnownName):
    pass


class Element:
    def emit(self) -> Sequence[str]:
        raise NotImplementedError()


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']


@dataclass
class Expression(Element):
    target_type: TargetType
    target: Register


@dataclass
class Checkpoint(Expression):
    arg: int

    def __init__(self, args: Sequence[Expression]):
        lg.debug(f'Checkpoint {args}')

        if len(args) != 1:
            raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

        arg = args[0]

        if not isinstance(arg, ConstantExpression):
            raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

        self.target_type = 'unit'
        self.target = None

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

    def __init__(self, args: Sequence[Expression]):
        lg.debug(f'Assertion {args}')

        if len(args) != 2:
            raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

        self.source = args[0]
        value_expr = args[1]

        if not isinstance(value_expr, ConstantExpression):
            raise UserWarning(f"'assertion' expects a constant value, got {value_expr}")

        if self.source.target_type != 'uint32':
            raise UserWarning(
                f"'assertion' expects a uint32 source, got {self.source.target_type}"
            )

        if value_expr.target_type != 'uint32':
            raise UserWarning(
                f"'assertion' expects a uint32 value, got {value_expr.target_type}"
            )

        self.target_type = 'unit'
        self.target = None

        # Inlining the value
        self.value = value_expr.value

    def emit(self) -> Sequence[str]:
        return flatten([
            '// Assertion',
            self.source.emit(),
            f'.assert {self.source.target} {self.value}'
        ])


@dataclass
class GlobalVariableCreate(Element):
    name: str

    def emit(self):
        return [
            f'// Begin variable {self.name}',
            f'{self.name}:',        # label
            'nop',                  # placeholder
            '// End variable',
        ]


@dataclass
class ConstantExpression(Expression):
    value: int

    def emit(self):
        return f'ldc {self.value} {self.target}'


@dataclass
class GlobalVarAssignment(Element):
    target: KnownName
    expr: Expression
    source: Register = DEFAULT_REGISTER

    def emit(self):
        return flatten([
            f"// Calculating {self.target.name} into {self.source}",
            self.expr.emit(),
            f'// Storing {self.target.name}',
            f'ldr &{self.target.name} b',
            f'mrm {self.source} b'
        ])


@dataclass
class GlobalVariableLoad(Expression):
    name: str

    def emit(self):
        return flatten([
            f'// Loading {self.name} address',
            f'ldr &{self.name} b',
            f'// Setting {self.name} to {self.target}',
            f'mmr b {self.target}'
        ])
