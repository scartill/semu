from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Literal, Any, cast
from dataclasses import dataclass
import ast

import click

from semu.pysemu.flatten import flatten


REGISTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)


class Element:
    def emit(self) -> Sequence[str]:
        raise NotImplementedError()


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']


@dataclass
class Checkpoint(Element):
    arg: int

    def emit(self) -> Sequence[str]:
        return [f'.check {self.arg}']


TargetType = Literal['unit', 'uint32']


@dataclass
class KnownName:
    name: str
    target_type: TargetType


@dataclass
class Constant(KnownName):
    value: Any


@dataclass
class GlobalVar(KnownName):
    pass


@dataclass
class LocalVar(KnownName):
    pass


class Namespace:
    names: Dict[str, KnownName]

    def __init__(self, name: str, parent: 'Namespace | None'):
        self.name = name
        self.parent = parent
        self.names = dict()

    def namespace(self) -> str:
        prefix = self.parent.parent_prefix() if self.parent else ''
        return f'{prefix}{self.name}'

    def parent_prefix(self) -> str:
        return f'{self.namespace()}.'

    def get_name(self, name: str) -> KnownName | None:
        lg.debug(f'Looking up {name} in {self.namespace()}')
        return self.names.get(name)

    def create_variable(self, name: str, target_type: TargetType) -> None:
        raise NotImplementedError()


@dataclass
class GlobalVarAssignment(Element):
    target: KnownName
    body: Sequence[Element]

    def emit(self):
        return flatten([
            f'// Calculating {self.target.name}',
            flatten([expr.emit() for expr in self.body]),
            f'ldr &{self.target.name} b',
            'mrm a b'
        ])


@dataclass
class ConstantExpression(Element):
    value: int

    def emit(self):
        return f'ldc {self.value} a'


class Function(Namespace, Element):
    name: str
    args: Sequence[str]
    body: Sequence[Element]

    def __init__(self, name: str, parent: Namespace):
        super().__init__(name, parent)
        self.args = list()
        self.body = list()

    def _emit_args(self, inx: int):
        arg = self.args[inx]
        reg = REGISTERS[inx]

        return [
            f'// {arg}',
            f'push {reg}'
        ]

    def emit(self) -> Sequence[str]:
        return flatten([
            f'// function {self.name}',
            [self._emit_args(i) for i in range(len(self.args))],
            [expr.emit() for expr in self.body]
        ])


class Module(Namespace, Element):
    functions: Dict[str, Function]
    body: Sequence[Element]

    def __init__(self, name: str, parent: Namespace):
        super().__init__(name, parent)
        self.functions = dict()
        self.body = list()

    def emit_global_var(self, global_var: GlobalVar):
        lg.debug(f'Defining a global variable placeholder {global_var.name}')

        return [
            f'// Begin variable {global_var.target_type}',
            f'{global_var.name}:',  # label
            'nop',                  # placeholder
            '// End variable',
        ]

    def create_variable(self, name: str, target_type: TargetType) -> None:
        if name in self.names:
            raise UserWarning(f'Redefinition of the name {name}')

        lg.debug(f'Creating a global variable {name}')
        self.names[name] = GlobalVar(name, target_type)

    def emit(self):
        result: Sequence[str] = []

        for global_var in filter(lambda n: isinstance(n, GlobalVar), self.names.values()):
            result.extend(self.emit_global_var(cast(GlobalVar, global_var)))

        for function in self.functions.values():
            result.extend(function.emit())

        for expr in self.body:
            result.extend(expr.emit())

        result.append('hlt')
        return flatten(result)


class TopLevel(Namespace, Element):
    modules: Dict[str, Module]

    def __init__(self):
        super().__init__('::', None)
        self.modules = dict()

    def namespace(self) -> str:
        return '::'

    def parent_prefix(self) -> str:
        return self.namespace()

    def emit(self):
        result: Sequence[str] = []

        for module in self.modules.values():
            result.extend(module.emit())

        return flatten(result)


def uint32const(ast_value: ast.AST):
    if isinstance(ast_value, ast.Constant) and isinstance(ast_value.value, int):
        value = ast_value.value

        if value < 0 or value > 0xFFFFFFFF:
            raise UserWarning(f'Int argument {ast_value} out of range')

        return value
    else:
        raise UserWarning(f'Unsupported const int argument {ast_value}')


def std_checkpoint(ast_args: Sequence[ast.expr]):
    if len(ast_args) != 1:
        raise UserWarning(f'checkpoint expects 1 argument, got {len(ast_args)}')

    arg = uint32const(ast_args[0])
    return ('unit', [Checkpoint(arg)])


STD_LIB_CALLS = {
    'checkpoint': std_checkpoint
}


class Translator:
    context: Namespace

    def __init__(self):
        self.context = TopLevel()

    def resolve_name(self, name: str) -> KnownName:
        known_name = self.context.get_name(name)

        if known_name is None:
            raise UserWarning(f'Unknown reference {name}')

        return known_name

    def translate_std_call(self, std_name: str, ast_args: Sequence[ast.expr]):
        if std_name not in STD_LIB_CALLS:
            raise UserWarning(f'Unknown stdlib call {std_name}')

        return STD_LIB_CALLS[std_name](ast_args)

    def translate_call(self, ast_call: ast.Call):
        ast_name = ast_call.func

        if not isinstance(ast_name, ast.Attribute):
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

        ast_name_name = cast(ast.Name, ast_name.value)

        if ast_name_name.id == 'stdlib':
            return self.translate_std_call(ast_name.attr, ast_call.args)
        else:
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

    def load_const(self, name: str):
        ''' Invalidates registers and stores the result in 'a' '''
        known_name = self.resolve_name(name)

        if not isinstance(known_name, Constant):
            raise UserWarning(f'Unsupported const reference {name}')

        return ('uint32', [ConstantExpression(known_name.value)])

    def translate_expr(self, ast_expr: ast.expr):
        ''' Invalidates registers and stores the result in 'a' '''

        if isinstance(ast_expr, ast.Constant):
            return ('uint32', [ConstantExpression(uint32const(ast_expr))])

        if isinstance(ast_expr, ast.Expr):
            if isinstance(ast_expr.value, ast.Call):
                return self.translate_call(ast_expr.value)

        if isinstance(ast_expr, ast.Name):
            if ast_expr.id.isupper():
                return self.load_const(ast_expr.id)

        raise UserWarning(f'Unsupported expression {ast_expr}')

    def translate_const_assign(self, name: str, ast_value: ast.AST):
        value = uint32const(ast_value)
        self.context.names[name] = Constant(name, 'uint32', value)
        return [VoidElement(f'Const {name} = {value}')]

    def translate_var_assign(self, target_name: str, source: ast.expr):
        ''' Invalidates registers and stores the result in 'a' '''
        target = self.resolve_name(target_name)

        if isinstance(target, GlobalVar):
            expr_target_type, expr_body = self.translate_expr(source)

            if target.target_type != expr_target_type:
                raise UserWarning(
                    f'Expression type mismath {expr_target_type} in not {target.target_type}'
                )

            return [GlobalVarAssignment(target, expr_body)]
        else:
            raise UserWarning(f'Unsupported assignment {target}')

    def translate_assign(self, ast_assign: ast.Assign):
        if len(ast_assign.targets) != 1:
            raise UserWarning(f'Assign expects 1 target, got {len(ast_assign.targets)}')

        ast_target = ast_assign.targets[0]

        if isinstance(ast_target, ast.Name):
            name = ast_target.id
        else:
            raise UserWarning(f'Unsupported assign target {ast_target}')

        ast_value = ast_assign.value

        if name.isupper():
            if not isinstance(ast_value, ast.Constant):
                raise UserWarning(f'Only const assignments are supported for {name}')

            return self.translate_const_assign(name, ast_value)
        elif name.islower():
            return self.translate_var_assign(name, ast_value)
        else:
            raise UserWarning(f'Unsupported name {name}')

    def translate_ann_assign(self, assign: ast.AnnAssign):
        if assign.simple != 1:
            raise UserWarning('Only simple type declarations are supported')

        name = cast(ast.Name, assign.target).id
        type_name = cast(ast.Name, assign.annotation).id

        if type_name == 'int':
            target_type = 'uint32'
        else:
            raise UserWarning('Only "int" type is supported')

        self.context.create_variable(name, target_type)
        return [VoidElement(f'Declare var {name}')]

    def translate_stmt(self, ast_element: ast.stmt) -> Sequence[Element]:
        if isinstance(ast_element, ast.expr):
            target_type, body = self.translate_expr(ast_element)
            lg.debug(f'Expression target type {target_type} ignored')
            return body
        elif isinstance(ast_element, ast.Pass):
            return [VoidElement('pass')]
        elif isinstance(ast_element, ast.Assign):
            return self.translate_assign(ast_element)
        elif isinstance(ast_element, ast.AnnAssign):
            return self.translate_ann_assign(ast_element)
        else:
            lg.warning(f'Unsupported element {ast_element}')
            return [VoidElement('unsupported')]

    def translate_body(self, ast_body: Sequence[ast.stmt]) -> Sequence[Element]:
        return flatten(list(map(self.translate_stmt, ast_body)))

    def translate_function(self, ast_function: ast.FunctionDef) -> Function:
        name = ast_function.name
        lg.debug(f'Function {name} found')
        function = Function(name, self.context)
        self.context = function

        if len(ast_function.args.args) > NUMBER_OF_REGISTERS:
            raise UserWarning(f'Function {name} has too many arguments')

        def make_arg(ast_arg: ast.arg):
            return ast_arg.arg

        function.args = [make_arg(ast_arg) for ast_arg in ast_function.args.args]
        function.body = self.translate_body(ast_function.body)
        self.context = cast(Namespace, function.parent)
        return function

    def translate_module(self, name: str, ast_module: ast.Module):
        module = Module(name, self.context)
        self.context = module

        ast_module_body: Sequence[ast.stmt] = []

        for ast_element in ast_module.body:
            if isinstance(ast_element, ast.FunctionDef):
                function = self.translate_function(ast_element)
                module.functions[function.name] = function
            else:
                ast_module_body.append(ast_element)

        module.body = self.translate_body(ast_module_body)
        self.context = cast(Namespace, module.parent)
        return module


def translate_string(module_name: str, input: str):
    ast_module = ast.parse(input)
    module = Translator().translate_module(module_name, ast_module)
    result = module.emit()
    return '\n'.join(filter(lambda s: s != '\n', result))


@click.command()
@click.option('-v', '--verbose', is_flag=True, help='sets logging level to debug')
@click.argument('input', type=Path)
@click.argument('output', type=Path)
def translate(verbose: bool, input: Path, output: Path):
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)
    lg.info(f'Translating {input} to {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(translate_string(input.stem, input.read_text()))


if __name__ == '__main__':
    translate()
