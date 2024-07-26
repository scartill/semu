import sys
from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Literal, Any, Tuple, cast
from dataclasses import dataclass
import ast

import click

from semu.pseudopython.flatten import flatten


REGISTERS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)
DEFAULT_REGISTER = 'a'
Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] | None


class Element:
    def emit(self) -> Sequence[str]:
        raise NotImplementedError()


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']


TargetType = Literal['unit', 'uint32']


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
        return [f'.check {self.arg}']


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


def uint32const(ast_value: ast.AST):
    if isinstance(ast_value, ast.Constant) and isinstance(ast_value.value, int):
        value = ast_value.value

        if value < 0 or value > 0xFFFFFFFF:
            raise UserWarning(f'Int argument {ast_value} out of range')

        return value
    else:
        raise UserWarning(f'Unsupported const int argument {ast_value}')


STD_LIB_CALLS = {
    'checkpoint': Checkpoint,
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

    def translate_std_call(self, std_name: str, args: Sequence[Expression]):
        if std_name not in STD_LIB_CALLS:
            raise UserWarning(f'Unknown stdlib call {std_name}')

        return STD_LIB_CALLS[std_name](args)

    def translate_arg(self, ast_arg: ast.AST, target: Register):
        return self.translate_source(ast_arg, target)

    def translate_call(self, ast_call: ast.Call):
        ast_name = ast_call.func

        if not isinstance(ast_name, ast.Attribute):
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

        ast_name_name = cast(ast.Name, ast_name.value)

        ast_args = ast_call.args

        if len(ast_args) > NUMBER_OF_REGISTERS:
            raise UserWarning(f'Function call {ast_name_name.id} has too many arguments')

        args_expressions: Sequence[Expression] = []
        for i in range(len(ast_args)):
            ast_arg = ast_args[i]
            target = cast(Register, REGISTERS[i])
            lg.debug(f'Adding argument of type {type(ast_arg)} to {target}')
            args_expressions.append(self.translate_arg(ast_arg, target))

        if ast_name_name.id == 'stdlib':
            return self.translate_std_call(ast_name.attr, args_expressions)
        else:
            raise UserWarning(f'Unsupported call {ast_call} {ast_name}')

    def load_const(self, name: str, target: Register):
        ''' Invalidates registers and stores the result in '<target>' '''
        known_name = self.resolve_name(name)

        if not isinstance(known_name, Constant):
            raise UserWarning(f'Unsupported const reference {name}')

        return ConstantExpression(
            target_type=known_name.target_type,
            value=known_name.value,
            target=target
        )

    def load_variable(self, name: str, target: Register):
        ''' Invalidates registers and stores the result in '<target>' '''
        known_name = self.resolve_name(name)
        return self.context.load_variable(known_name, target)

    def translate_expr(self, ast_expr: ast.Expression, target: Register) -> Expression:
        ''' Invalidates registers and stores the result in '<target>' '''

        if isinstance(ast_expr, ast.Constant):
            lg.debug('Constant expression')

            return ConstantExpression(
                target_type='uint32',
                value=uint32const(ast_expr),
                target=target
            )

        if isinstance(ast_expr, ast.Call):
            lg.debug('Call expression')
            return self.translate_call(ast_expr)

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

    def translate_source(self, source: ast.AST, target: Register):
        lg.debug('Source')

        if isinstance(source, ast.Expression):
            return self.translate_expr(source, target)

        if isinstance(source, ast.Constant):
            return ConstantExpression(
                target_type='uint32',
                value=uint32const(source),
                target=target
            )

        if isinstance(source, ast.Name):
            if source.id.isupper():
                return self.load_const(source.id, target)
            else:
                return self.load_variable(source.id, target)

        raise UserWarning(f'Unsupported assignment source {source}')

    def translate_var_assign(self, target_name: str, source: ast.AST):
        ''' Invalidates registers and stores the result in
            the register `GlobalVarAssignment.source`
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
        lg.debug('Assign')

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
        return VoidElement(f'Declare var {name}')

    def translate_stmt(self, ast_element: ast.stmt) -> Element:
        lg.debug(f'Stmt {type(ast_element)}')

        if isinstance(ast_element, ast.Expr):
            if isinstance(ast_element.value, ast.Expression):
                expression = self.translate_expr(ast_element.value, DEFAULT_REGISTER)
                return expression
            if isinstance(ast_element.value, ast.Call):
                return self.translate_call(ast_element.value)
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
