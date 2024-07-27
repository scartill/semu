import sys
from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Any, Tuple, cast
from dataclasses import dataclass
import ast

import click

from semu.pseudopython.flatten import flatten

from semu.pseudopython.elements import (
    REGISTERS, DEFAULT_REGISTER, NUMBER_OF_REGISTERS,
    TargetType, Register,
    KnownName, Constant, GlobalVar,
    Element, VoidElement, Expression, ConstantExpression,
    GlobalVariableCreate, GlobalVarAssignment, GlobalVariableLoad,
    Checkpoint, Assertion, BoolToInt
)

import semu.pseudopython.binops as binops


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

    def load_variable(self, known_name: KnownName, target: Register) -> Expression:
        raise NotImplementedError()


class Function(Namespace, Element):
    name: str
    args: Sequence[str]
    body: Sequence[Element]

    def __init__(self, name: str, parent: Namespace):
        super().__init__(name, parent)
        self.args = list()
        self.body = list()

    def _emit_arg(self, inx: int):
        arg = self.args[inx]
        reg = REGISTERS[inx]

        return [
            f'// {arg}',
            f'push {reg}'
        ]

    def emit(self) -> Sequence[str]:
        return flatten([
            f'// function {self.name}',
            [self._emit_arg(i) for i in range(len(self.args))],
            [expr.emit() for expr in self.body]
        ])

    def __str__(self) -> str:
        result = [f'Function {self.namespace()}']

        result.append('Arguments:')
        for arg in self.args:
            result.append(f'\t{arg}')

        result.extend(['Body:'])
        for expr in self.body:
            result.append(str(expr))

        return '\n'.join(result)


@dataclass
class Module(Namespace, Element):
    functions: Dict[str, Function]
    body: Sequence[Element]

    def __init__(self, name: str, parent: Namespace):
        super().__init__(name, parent)
        self.functions = dict()
        self.body = list()

    def create_global_var(self, global_var: GlobalVar):
        return GlobalVariableCreate(global_var.name)

    def create_variable(self, name: str, target_type: TargetType) -> None:
        if name in self.names:
            raise UserWarning(f'Redefinition of the name {name}')

        lg.debug(f'Creating a global variable {name}')
        self.names[name] = GlobalVar(name, target_type)

    def load_variable(self, known_name: KnownName, target: Register) -> Expression:
        return GlobalVariableLoad(
            name=known_name.name,
            target_type=known_name.target_type,
            target=target
        )

    def emit(self):
        result: Sequence[str] = []

        for global_var in filter(lambda n: isinstance(n, GlobalVar), self.names.values()):
            element = self.create_global_var(cast(GlobalVar, global_var))
            result.extend(element.emit())

        for function in self.functions.values():
            result.extend(function.emit())

        for expr in self.body:
            result.extend(expr.emit())

        result.append('hlt')
        return flatten(result)

    def __str__(self) -> str:
        result = ['Module[', f'\tname={self.name}']

        if self.names:
            result.append('\tKnownNames=[')

            for known_name in self.names.values():
                result.append(f'\t\t{str(known_name)}')

            result.append('\t]')

        if self.functions:
            result.append('\tFunctions=[')

            for function in self.functions.values():
                result.append(f'\t\t{str(function)}')

            result.append('\t]')

        if self.body:
            result.append('\tBody=[')

            for statement in self.body:
                result.append(f'\t\t{str(statement)}')

            result.append('\t]')

        result.append(']')
        return '\n'.join(result)


@dataclass
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

    def __str__(self):
        return '\n'.join([str(module) for module in self.modules.values()])


def get_constant_type(ast_const: ast.Constant):
    if isinstance(ast_const.value, bool):
        return 'bool32'

    if isinstance(ast_const.value, int):
        return 'uint32'

    raise UserWarning(f'Unsupported constant type {type(ast_const.value)}')


def uint32const(ast_value: ast.AST):
    if isinstance(ast_value, ast.Constant) and isinstance(ast_value.value, int):
        value = ast_value.value

        if value < 0 or value > 0xFFFFFFFF:
            raise UserWarning(f'Int argument {ast_value} out of range')

        return value
    else:
        raise UserWarning(f'Unsupported const int argument {ast_value}')


def bool32const(ast_value: ast.AST):
    if isinstance(ast_value, ast.Constant) and isinstance(ast_value.value, bool):
        value = ast_value.value
        return value
    else:
        raise UserWarning(f'Unsupported const int argument {ast_value}')


def get_constant_value(target_type: TargetType, source: ast.AST):
    if target_type == 'uint32':
        return uint32const(source)

    if target_type == 'bool32':
        return bool32const(source)

    raise UserWarning(f'Unsupported constant type {target_type}')


def create_binop(left: Expression, right: Expression, op: ast.AST, target: Register):
    if left.target_type != right.target_type:
        raise UserWarning(f'Type mismatch {left.target_type} != {right.target_type}')

    target_type = left.target_type

    if target_type != 'uint32':
        raise UserWarning(f'Unsupported binop type {target_type}')

    Op = None

    if isinstance(op, ast.Add):
        Op = binops.Add

    if isinstance(op, ast.Sub):
        Op = binops.Sub

    if isinstance(op, ast.Mult):
        Op = binops.Mul

    if Op is None:
        raise UserWarning(f'Unsupported binop {op}')

    return Op(target_type, target, left, right)


STD_LIB_CALLS = {
    'checkpoint': Checkpoint,
    'assert_eq': Assertion,
    'bool_to_int': BoolToInt
}


class Translator:
    context: Namespace

    def __init__(self):
        top_level = TopLevel()
        self.context = top_level
        self._top = top_level

    def resolve_name(self, name: str) -> KnownName:
        known_name = self.context.get_name(name)

        if known_name is None:
            raise UserWarning(f'Unknown reference {name}')

        return known_name

    def translate_std_call(
            self, std_name: str,
            args: Sequence[Expression], target: Register
    ):
        if std_name not in STD_LIB_CALLS:
            raise UserWarning(f'Unknown stdlib call {std_name}')

        return STD_LIB_CALLS[std_name](args, target)

    def translate_arg(self, ast_arg: ast.AST, target: Register):
        return self.translate_source(ast_arg, target)

    def translate_call(self, ast_call: ast.Call, target: Register):
        ast_name = ast_call.func

        if not isinstance(ast_name, ast.Attribute):
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

        ast_name_name = cast(ast.Name, ast_name.value)
        lg.debug(f'Call {ast_name_name.id}.{ast_name.attr}')

        ast_args = ast_call.args

        if len(ast_args) > NUMBER_OF_REGISTERS:
            raise UserWarning(f'Function call {ast_name_name.id} has too many arguments')

        args_expressions: Sequence[Expression] = []
        for i in range(len(ast_args)):
            ast_arg = ast_args[i]
            target = REGISTERS[i]
            lg.debug(f'Adding argument of type {type(ast_arg)} to reg:{target}')
            args_expressions.append(self.translate_arg(ast_arg, target))

        if ast_name_name.id == 'std':
            return self.translate_std_call(ast_name.attr, args_expressions, target)
        else:
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

    def load_const(self, name: str, target: Register):
        known_name = self.resolve_name(name)

        if not isinstance(known_name, Constant):
            raise UserWarning(f'Unsupported const reference {name}')

        return ConstantExpression(
            target_type=known_name.target_type,
            value=known_name.value,
            target=target
        )

    def load_variable(self, name: str, target: Register):
        known_name = self.resolve_name(name)
        return self.context.load_variable(known_name, target)

    def translate_expr(self, ast_expr: ast.Expression, target: Register) -> Expression:
        if isinstance(ast_expr, ast.Constant):
            lg.debug('Constant expression')

            return ConstantExpression(
                target_type='uint32',
                value=uint32const(ast_expr),
                target=target
            )

        if isinstance(ast_expr, ast.Call):
            lg.debug('Call expression')
            return self.translate_call(ast_expr, target)

        if isinstance(ast_expr, ast.Name):
            if ast_expr.id.isupper():
                return self.load_const(ast_expr.id, target)
            else:
                return self.load_variable(ast_expr.id, target)

        raise UserWarning(f'Unsupported expression {ast_expr}')

    def translate_const_assign(self, name: str, ast_value: ast.Constant):
        value = uint32const(ast_value)
        self.context.names[name] = Constant(name, 'uint32', value)
        return VoidElement(f'Const {name} = {value}')

    def translate_source(self, source: ast.AST, target: Register) -> Expression:
        if isinstance(source, ast.Expression):
            lg.debug('Source from expression')
            return self.translate_expr(source, target)

        if isinstance(source, ast.Constant):
            lg.debug(f'Source from constant (type {type(source.value)})')
            target_type = get_constant_type(source)
            lg.debug(f'Detected target type = {target_type}')
            value = get_constant_value(target_type, source)

            return ConstantExpression(
                target_type=target_type,
                value=value,
                target=target
            )

        if isinstance(source, ast.Name):
            lg.debug('Source from name')

            if source.id.isupper():
                return self.load_const(source.id, target)
            else:
                return self.load_variable(source.id, target)

        if isinstance(source, ast.BinOp):
            lg.debug('Source from binop')
            left = self.translate_source(source.left, REGISTERS[0])
            right = self.translate_source(source.right, REGISTERS[1])
            return create_binop(left, right, source.op, target)

        if isinstance(source, ast.Call):
            lg.debug('Source from a call')
            return self.translate_call(source, target)

        raise UserWarning(f'Unsupported assignment source {source}')

    def translate_var_assign(self, target_name: str, source: ast.AST):
        '''
            Stores the result the `GlobalVarAssignment.source` register
        '''
        target = self.resolve_name(target_name)

        if isinstance(target, GlobalVar):
            expression = self.translate_source(source, GlobalVarAssignment.source)
            t_type = target.target_type
            e_type = expression.target_type

            if t_type != e_type:
                raise UserWarning(
                    f'Expression type mismath {e_type} in not {t_type}'
                )

            return GlobalVarAssignment(target, expression)
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
        elif type_name == 'bool':
            target_type = 'bool32'
        else:
            raise UserWarning(f'Unsupported type found ({type_name})')

        self.context.create_variable(name, target_type)
        return VoidElement(f'Declare var {name}: {target_type}')

    def translate_stmt(self, ast_element: ast.stmt) -> Element:
        ''' NB: Statement execution invalidates all registers.
            Within a statement, each element is responsible for keeping
            its own registers consistent.
        '''
        lg.debug(f'Stmt {type(ast_element)}')

        if isinstance(ast_element, ast.Expr):
            if isinstance(ast_element.value, ast.Expression):
                expression = self.translate_expr(ast_element.value, DEFAULT_REGISTER)
                return expression
            if isinstance(ast_element.value, ast.Call):
                return self.translate_call(ast_element.value, DEFAULT_REGISTER)
            else:
                lg.debug(f'Statements of type {type(ast_element.value)} are ignored')
                return VoidElement('ignored')
        elif isinstance(ast_element, ast.Pass):
            return VoidElement('pass')
        elif isinstance(ast_element, ast.Assign):
            return self.translate_assign(ast_element)
        elif isinstance(ast_element, ast.AnnAssign):
            return self.translate_ann_assign(ast_element)
        else:
            lg.warning(f'Unsupported element {ast_element} ({type(ast_element)})')
            return VoidElement('unsupported')

    def translate_body(self, ast_body: Sequence[ast.stmt]) -> Sequence[Element]:
        return list(map(self.translate_stmt, ast_body))

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

    def translate(self, name: str, ast_module: ast.Module):
        module = self.translate_module(name, ast_module)
        cast(TopLevel, self.context).modules[name] = module

    def top(self) -> TopLevel:
        return self._top


def eprint(*args: Any, **kwargs: Any):
    print(*args, file=sys.stderr, **kwargs)


Params = Dict[str, Any]


def emit(params: Params, translator: Translator):
    top = translator.top()

    results: Sequence[Tuple[str, str]] = []
    for module_name, module in top.modules.items():
        module_sasm = '\n'.join(module.emit())

        if params['verbose']:
            eprint(f'------------ AST {module_name} ---------------')
            eprint(top)
            eprint(f'------------ ASM {module_name} ---------------')
            eprint(module_sasm)
            eprint('-----------------------------------------------')

        results.append((module_name, module_sasm))

    return results


def add_module(translator: Translator, name: str, input: str):
    ast_tree = ast.parse(input)
    translator.translate(name, ast_tree)


def compile_single_str(params: Params, name: str, input: str):
    translator = Translator()
    add_module(translator, name, input)
    sasm = emit(params, translator)
    return sasm


def compile_single_file(params: Params, input: Path, output: Path):
    sasm = compile_single_str(params, input.stem, input.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sasm[0][1])


@click.command()
@click.pass_context
@click.option('-v', '--verbose', is_flag=True, help='sets logging level to debug')
@click.argument('input', type=Path)
@click.argument('output', type=Path, required=False)
def compile(ctx: click.Context, verbose: bool, input: Path, output: Path | None):
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)

    if not output:
        output = input.with_suffix('.sasm')

    lg.info(f'Translating {input} to {output}')
    compile_single_file(ctx.obj, input, output)


if __name__ == '__main__':
    compile()
