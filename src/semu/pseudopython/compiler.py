import sys
from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Any, List, cast
import ast
import json

import click

import semu.pseudopython.pptypes as t
import semu.pseudopython.base as b
import semu.pseudopython.expressions as ex
import semu.pseudopython.flow as flow
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls
import semu.pseudopython.modules as mods
import semu.pseudopython.packages as pack
import semu.pseudopython.arrays as arr
import semu.pseudopython.helpers as h
import semu.pseudopython.factories as f
import semu.pseudopython.extranslator as et


# Late binding
calls.Function.factory = f.create_function
cls.Class.fun_factory = f.create_function
cls.Class.method_factory = f.create_method
mods.Module.fun_factory = f.create_function
mods.Module.global_var_factory = f.create_global_variable


class Translator(et.ExpressionTranslator):
    top_level: pack.TopLevel
    settings: h.CompileSettings

    def __init__(self, settings: h.CompileSettings):
        top_level = pack.TopLevel()
        super().__init__(top_level)
        self.settings = settings
        self.top_level = top_level

    def tx_const_assign(self, name: str, ast_value: ast.AST):
        if not isinstance(ast_value, ast.Constant):
            raise UserWarning(
                f'Only const assignments are supported for {name}'
            )

        value = h.int32const(ast_value)
        self.context.add_name(b.Constant(self.context, name, t.Int32, value))
        return b.VoidElement(f'Const {name} = {value}')

    def tx_assign(self, ast_assign: ast.Assign):
        if len(ast_assign.targets) != 1:
            raise UserWarning(f'Assign expects 1 target, got {len(ast_assign.targets)}')

        ast_target = ast_assign.targets[0]
        ast_value = ast_assign.value
        source = self.tx_phy_expression(ast_value)

        if isinstance(ast_target, ast.Subscript):
            array = self.resolve_object(ast_target.value).known_name
            index = self.tx_phy_expression(ast_target.slice)

            if isinstance(array, arr.GlobalArray):
                return h.array_assign(array, index, source)

            raise UserWarning('Subscript not supported')
        else:
            target = self.resolve_object(ast_target).known_name
            return h.simple_assign(target, source)

    def tx_type(self, ast_type: ast.AST):
        pp_expr = self.tx_expression(ast_type)

        if not isinstance(pp_expr, ex.TypeWrapper):
            raise UserWarning(f'Unsupported type expression {pp_expr}')

        return pp_expr.pp_type

    def tx_ann_assign(self, assign: ast.AnnAssign):
        if assign.simple != 1:
            raise UserWarning('Only simple type declarations are supported')

        if not isinstance(assign.target, ast.Name):
            raise UserWarning('Unsupported type declaration')

        pp_type = self.tx_type(assign.annotation)
        return self.context.create_variable(assign.target.id, pp_type)

    def tx_if(self, ast_if: ast.If):
        test = self.tx_phy_expression(ast_if.test)
        true_body = self.tx_body(ast_if.body)

        if test.pp_type != t.Bool32:
            raise UserWarning(f'If test must be of type bool32, got {test.pp_type}')

        if ast_if.orelse:
            false_body = self.tx_body(ast_if.orelse)
        else:
            false_body = [b.VoidElement('no else')]

        return flow.If(test, true_body, false_body)

    def tx_while(self, ast_while: ast.While):
        test = self.tx_expression(ast_while.test)
        body = self.tx_body(ast_while.body)

        if not isinstance(test, ex.PhyExpression):
            raise UserWarning(f'While test must be a physical expression, got {test}')

        if test.pp_type != t.Bool32:
            raise UserWarning(f'While test must be of type bool32, got {test.pp_type}')

        return flow.While(test, body)

    def tx_free_is(self, ast_is: ast.Compare):
        if len(ast_is.ops) != 1:
            raise UserWarning(f'Unsupported number of compare ops {len(ast_is.ops)}')

        op = ast_is.ops[0]

        if not isinstance(op, ast.Is):
            raise UserWarning(f'Unsupported free op {op}')

        if not isinstance(ast_is.left, ast.Name):
            raise UserWarning(f'Unsupported free left {ast_is.left}')

        name = ast_is.left.id
        return self.tx_const_assign(name, ast_is.comparators[0])

    def tx_import_name(self, names: List[str]) -> b.KnownName | None:
        (found, namespace, name, rest_names) = h.find_module(self.top_level, names)

        lg.debug(f'Module lookup result: {found} ({namespace}.{name})')

        if found:
            # Already imported
            return None

        parent, name, ast_module = h.load_module(self.settings, namespace, name, rest_names)

        lg.debug(f'Importing module {name} to {parent.namespace()}')

        current_context = self.context
        self.context = parent
        module = self.tx_module(name, ast_module)
        parent.add_name(module)
        self.context = current_context
        return module

    def tx_import(self, ast_import: ast.Import):
        for alias in ast_import.names:
            self.tx_import_name(alias.name.split('.'))

        return b.VoidElement('import')

    def tx_class(self, ast_class: ast.ClassDef):
        classdef = cls.Class(ast_class.name, self.context)
        self.context.add_name(classdef)
        self.context = classdef

        for ast_statement in ast_class.body:
            if not isinstance(ast_statement, (ast.FunctionDef, ast.AnnAssign, ast.Pass)):
                raise UserWarning(f'Unsupported class statement {ast_statement}')

            self.tx_stmt(ast_statement)

        self.context = cast(ns.Namespace, classdef.parent)
        return classdef

    def tx_return(self, ast_return: ast.Return) -> b.Element:
        if isinstance(self.context, calls.Function):
            func = self.context
        else:
            raise UserWarning('Return statement outside a function')

        if ast_return.value:
            value = self.tx_expression(ast_return.value)
            f_type = func.return_type
            e_type = value.pp_type

            if f_type != e_type:
                raise UserWarning(f'Return type mismatch {f_type} != {e_type}')

            if not isinstance(value, ex.PhyExpression):
                raise UserWarning(f'Unsupported return value {value}')

            func.returns = True
            return calls.ReturnValue(func, value)
        else:
            if func.return_type != t.Unit:
                raise UserWarning('Function has no target type')

            return calls.ReturnUnit(func)

    def tx_function(self, ast_function: ast.FunctionDef):
        name = ast_function.name

        lg.debug(f'Found function {name}')

        if ast_function.returns is None:
            pp_type = t.Unit
        else:
            pp_type = self.tx_type(ast_function.returns)

        args = []
        for ast_arg in ast_function.args.args:
            if ast_arg.annotation is None:
                raise UserWarning(f'Argument {ast_arg.arg} has no type')

            arg_name = ast_arg.arg
            arg_type = self.tx_type(ast_arg.annotation)
            args.append((arg_name, arg_type))

        decors = [
            self.tx_expression(ast_decor)
            for ast_decor in ast_function.decorator_list
        ]

        function = self.context.create_function(name, args, decors, pp_type)
        self.context = function
        assert isinstance(function, calls.Function)
        function.body = self.tx_body(ast_function.body)
        h.validate_function(function)
        self.context = cast(ns.Namespace, function.parent)
        return function

    def tx_stmt(self, ast_element: ast.stmt) -> b.Element:
        match type(ast_element):
            case ast.Expr:
                value = cast(ast.Expr, ast_element).value

                if isinstance(value, ast.Compare):
                    # NB: This is a hack to support `is` as a free operator
                    return self.tx_free_is(value)
                else:
                    return self.tx_phy_expression(value)
            case ast.Pass:
                return b.VoidElement('pass')
            case ast.Assign:
                return self.tx_assign(cast(ast.Assign, ast_element))
            case ast.AnnAssign:
                return self.tx_ann_assign(cast(ast.AnnAssign, ast_element))
            case ast.If:
                return self.tx_if(cast(ast.If, ast_element))
            case ast.While:
                return self.tx_while(cast(ast.While, ast_element))
            case ast.FunctionDef:
                return self.tx_function(cast(ast.FunctionDef, ast_element))
            case ast.Return:
                return self.tx_return(cast(ast.Return, ast_element))
            case ast.ClassDef:
                return self.tx_class(cast(ast.ClassDef, ast_element))
            case ast.Import:
                return self.tx_import(cast(ast.Import, ast_element))

        lg.warning(f'Unsupported element {ast_element} ({type(ast_element)})')
        return b.VoidElement('unsupported')

    def tx_body(self, ast_body: Sequence[ast.stmt]) -> b.Elements:
        return cast(b.Elements, list(filter(
            lambda x: isinstance(x, b.Element),
            (self.tx_stmt(ast_element) for ast_element in ast_body)
        )))

    def tx_module(self, name: str, ast_module: ast.Module):
        module = mods.Module(name, self.context)
        self.context = module
        module.body = self.tx_body(ast_module.body)
        self.context = cast(ns.Namespace, module.parent)
        return module

    def translate(self, name: str, ast_module: ast.Module):
        module = self.tx_module(name, ast_module)
        assert isinstance(self.context, pack.TopLevel)
        self.context.add_name(module)
        self.context.main = module

    def top(self) -> pack.TopLevel:
        return self.top_level


def eprint(*args: Any, **kwargs: Any):
    print(*args, file=sys.stderr, **kwargs)


Params = Dict[str, Any]


def emit(settings: h.CompileSettings, translator: Translator):
    top = translator.top()

    if settings.produce_ast:
        eprint('------------------ AST -----------------------')
        eprint(json.dumps(top.json(), indent=2))

    sasm = '\n'.join(top.emit())

    if settings.verbose:
        eprint('------------------ SASM ----------------------')
        eprint(sasm)
        eprint('----------------------------------------------')

    return sasm


def compile_string(settings: h.CompileSettings, name: str, input: str):
    translator = Translator(settings)
    ast_tree = ast.parse(input)
    translator.translate(name, ast_tree)
    sasm = emit(settings, translator)
    return sasm


def compile_file(settings: h.CompileSettings, input: Path, output: Path):
    sasm = compile_string(settings, input.stem, input.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sasm)


@click.command()
@click.pass_context
@click.option('-v', '--verbose', is_flag=True, help='Sets logging level to debug')
@click.option('--pp-path', type=str, help='Path to the pseudopython package')
@click.option('--produce-ast', is_flag=True, help='Produce AST output')
@click.argument('input', type=Path)
@click.argument('output', type=Path, required=False)
def compile(ctx: click.Context, input: Path, output: Path | None, **params):
    ctx.ensure_object(h.CompileSettings)
    ctx.obj.update(**params)

    lg.basicConfig(level=lg.DEBUG if ctx.obj.verbose else lg.INFO)

    if not output:
        output = input.with_suffix('.sasm')

    lg.info(f'Translating {input.name} to {output.name}')
    compile_file(ctx.obj, input, output)


if __name__ == '__main__':
    compile()
