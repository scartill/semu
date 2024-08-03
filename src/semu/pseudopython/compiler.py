import sys
from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Any, Tuple, cast
import ast

import click

from semu.pseudopython.elements import (
    REGISTERS, DEFAULT_REGISTER, Register,
    KnownName, Constant, GlobalVar,
    Element, VoidElement, Expression, Expressions,
    ConstantExpression, GlobalVarAssignment
)

import semu.pseudopython.builtins as builtins
import semu.pseudopython.flow as flow
import semu.pseudopython.helpers as helpers
import semu.pseudopython.namespaces as ns


class Translator:
    context: ns.Namespace

    def __init__(self):
        top_level = ns.TopLevel()
        self.context = top_level
        self._top = top_level

    def resolve_name(self, ast_name: ast.AST) -> KnownName:
        if not isinstance(ast_name, ast.Name):
            raise UserWarning(f'Unsupported name {ast_name}')

        name = ast_name.id
        known_name = self.context.get_name(name)

        if known_name is None:
            raise UserWarning(f'Unknown reference {name}')

        return known_name

    def translate_builtin_inline(
        self, known_name: builtins.BuiltinInline, args: Expressions,
        target: Register
    ):
        return known_name.func(known_name, args, target)

    def translate_real_call(self, function: ns.Function, args: Expressions, target: Register):
        return helpers.make_call(function, args, target)

    def translate_arg(self, ast_arg: ast.AST, target: Register):
        return self.translate_expression(ast_arg, target)

    def translate_call(self, ast_call: ast.Call, target: Register):
        ast_name = ast_call.func
        lg.debug(f'Raw call {ast_name}')

        known_name = self.resolve_name(ast_name)

        ast_args = ast_call.args

        args_expressions: Expressions = []
        for i in range(len(ast_args)):
            ast_arg = ast_args[i]
            target = REGISTERS[i]
            lg.debug(f'Adding argument of type {type(ast_arg)} to reg:{target}')
            args_expressions.append(self.translate_arg(ast_arg, target))

        if isinstance(known_name, builtins.BuiltinInline):
            return self.translate_builtin_inline(known_name, args_expressions, target)

        if isinstance(known_name, ns.Function):
            return self.translate_real_call(known_name, args_expressions, target)

        raise UserWarning(f'Unsupported call {ast_call}')

    def load_const(self, name: ast.AST, target: Register):
        known_name = self.resolve_name(name)

        if not isinstance(known_name, Constant):
            raise UserWarning(f'Unsupported const reference {name}')

        return ConstantExpression(
            target_type=known_name.target_type, value=known_name.value,
            target=target
        )

    def translate_const_assign(self, name: str, ast_value: ast.AST):
        if not isinstance(ast_value, ast.Constant):
            raise UserWarning(
                f'Only const assignments are supported for {name}'
            )

        value = helpers.int32const(ast_value)
        self.context.names[name] = Constant(name, 'int32', value)
        return VoidElement(f'Const {name} = {value}')

    def translate_boolop(self, source: ast.BoolOp, target: Register):
        values = source.values
        args = [self.translate_expression(value, DEFAULT_REGISTER) for value in values]
        return helpers.create_boolop(args, source.op, target)

    def translate_expression(self, source: ast.AST, target: Register) -> Expression:
        if isinstance(source, ast.Constant):
            lg.debug(f'Source from constant (type {type(source.value)})')
            target_type = helpers.get_constant_type(source)
            lg.debug(f'Detected target type = {target_type}')
            value = helpers.get_constant_value(target_type, source)

            return ConstantExpression(
                target_type=target_type, value=value,
                target=target
            )

        if isinstance(source, ast.Name) or isinstance(source, ast.Attribute):
            lg.debug('Source from name')
            known_name = self.resolve_name(source)

            if isinstance(known_name, Constant):
                return self.load_const(source, target)

            if isinstance(known_name, GlobalVar):
                return self.context.load_variable(known_name, target)

            raise UserWarning(f'Unsupported name {source}')

        if isinstance(source, ast.BinOp):
            lg.debug('Source from binop')
            left = self.translate_expression(source.left, REGISTERS[0])
            right = self.translate_expression(source.right, REGISTERS[1])
            return helpers.create_binop(left, right, source.op, target)

        if isinstance(source, ast.Call):
            lg.debug('Source from a call')
            return self.translate_call(source, target)

        if isinstance(source, ast.UnaryOp):
            lg.debug('Source from a unary op')
            right = self.translate_expression(source.operand, REGISTERS[0])
            return helpers.create_unary(right, source.op, target)

        if isinstance(source, ast.BoolOp):
            lg.debug('Source from a bool op')
            return self.translate_boolop(source, target)

        if isinstance(source, ast.Compare):
            lg.debug('Source from a compare')
            left = self.translate_expression(source.left, REGISTERS[0])
            ops = source.ops

            if len(source.comparators) != 1:
                raise UserWarning(
                    f'Unsupported number of comparators {len(source.comparators)}'
                )

            assert len(ops) == 1

            right = self.translate_expression(source.comparators[0], REGISTERS[1])
            return helpers.create_compare(left, ops[0], right, target)

        raise UserWarning(f'Unsupported assignment source {source}')

    def translate_global_var_assign(self, target: GlobalVar, source: ast.AST):
        '''
            Stores the result the `GlobalVarAssignment.source` register
        '''
        expression = self.translate_expression(source, GlobalVarAssignment.source)
        t_type = target.target_type
        e_type = expression.target_type

        if t_type != e_type:
            raise UserWarning(
                f'Expression type mismath {e_type} in not {t_type}'
            )

        return GlobalVarAssignment(target, expression)

    def translate_assign(self, ast_assign: ast.Assign):
        if len(ast_assign.targets) != 1:
            raise UserWarning(f'Assign expects 1 target, got {len(ast_assign.targets)}')

        ast_target = ast_assign.targets[0]
        ast_value = ast_assign.value
        known_name = self.resolve_name(ast_target)

        if isinstance(known_name, GlobalVar):
            return self.translate_global_var_assign(known_name, ast_value)
        else:
            raise UserWarning(f'Unsupported assignment target {known_name}')

    def translate_ann_assign(self, assign: ast.AnnAssign):
        if assign.simple != 1:
            raise UserWarning('Only simple type declarations are supported')

        if not isinstance(assign.target, ast.Name):
            raise UserWarning('Unsupported type declaration')

        name = assign.target.id

        if not isinstance(assign.annotation, ast.Name):
            raise UserWarning('External types are not supported')

        type_name = assign.annotation.id

        if type_name == 'int':
            target_type = 'int32'
        elif type_name == 'bool':
            target_type = 'bool32'
        else:
            raise UserWarning(f'Unsupported type found ({type_name})')

        return self.context.create_variable(name, target_type)

    def translate_if(self, ast_if: ast.If):
        test = self.translate_expression(ast_if.test, DEFAULT_REGISTER)
        true_body = self.translate_body(ast_if.body)

        if test.target_type != 'bool32':
            raise UserWarning(f'If test must be of type bool32, got {test.target_type}')

        if ast_if.orelse:
            false_body = self.translate_body(ast_if.orelse)
        else:
            false_body = [VoidElement('no else')]

        return flow.If(test, true_body, false_body)

    def translate_while(self, ast_while: ast.While):
        test = self.translate_expression(ast_while.test, DEFAULT_REGISTER)
        body = self.translate_body(ast_while.body)

        if test.target_type != 'bool32':
            raise UserWarning(f'While test must be of type bool32, got {test.target_type}')

        return flow.While(test, body)

    def translate_free_is(self, ast_is: ast.Compare):
        if len(ast_is.ops) != 1:
            raise UserWarning(f'Unsupported number of compare ops {len(ast_is.ops)}')

        op = ast_is.ops[0]

        if not isinstance(op, ast.Is):
            raise UserWarning(f'Unsupported free op {op}')

        if not isinstance(ast_is.left, ast.Name):
            raise UserWarning(f'Unsupported free left {ast_is.left}')

        name = ast_is.left.id
        return self.translate_const_assign(name, ast_is.comparators[0])

    def translate_stmt(self, ast_element: ast.stmt) -> Element:
        ''' NB: Statement execution invalidates all registers.
            Within a statement, each element is responsible for keeping
            its own registers consistent.
        '''
        lg.debug(f'Stmt {type(ast_element)}')

        match type(ast_element):
            case ast.Expr:
                value = cast(ast.Expr, ast_element).value

                if isinstance(value, ast.Compare):
                    # NB: This is a hack to support `is` as a free operator
                    return self.translate_free_is(value)
                else:
                    return self.translate_expression(value, DEFAULT_REGISTER)

            case ast.Pass:
                return VoidElement('pass')
            case ast.Assign:
                return self.translate_assign(cast(ast.Assign, ast_element))
            case ast.AnnAssign:
                return self.translate_ann_assign(cast(ast.AnnAssign, ast_element))
            case ast.If:
                return self.translate_if(cast(ast.If, ast_element))
            case ast.While:
                return self.translate_while(cast(ast.While, ast_element))
            case ast.FunctionDef:
                return self.translate_function(cast(ast.FunctionDef, ast_element))

        lg.warning(f'Unsupported element {ast_element} ({type(ast_element)})')
        return VoidElement('unsupported')

    def translate_body(self, ast_body: Sequence[ast.stmt]) -> Sequence[Element]:
        return list(map(self.translate_stmt, ast_body))

    def translate_function(self, ast_function: ast.FunctionDef):
        name = ast_function.name

        if ast_function.returns is None:
            target_type = 'unit'
        else:
            raise UserWarning(f'Unsupported target type {ast_function.returns}')

        lg.debug(f'Function {name} found')

        function = helpers.create_function(self.context, name, ast_function.args, target_type)
        self.context.names[name] = function
        self.context = function
        function.body = self.translate_body(ast_function.body)
        self.context = cast(ns.Namespace, function.parent)
        return function

    def translate_module(self, name: str, ast_module: ast.Module):
        module = ns.Module(name, self.context)
        self.context = module
        module.body = self.translate_body(ast_module.body)
        self.context = cast(ns.Namespace, module.parent)
        return module

    def translate(self, name: str, ast_module: ast.Module):
        module = self.translate_module(name, ast_module)
        cast(ns.TopLevel, self.context).modules[name] = module

    def top(self) -> ns.TopLevel:
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


def compile_single_string(params: Params, name: str, input: str):
    translator = Translator()
    add_module(translator, name, input)
    sasm = emit(params, translator)
    return sasm[0][1]


def compile_single_file(params: Params, input: Path, output: Path):
    sasm = compile_single_string(params, input.stem, input.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sasm)


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
