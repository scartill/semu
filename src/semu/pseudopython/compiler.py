import sys
from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Any, List, cast
import ast
import json

import click

import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs
import semu.pseudopython.names as n
import semu.pseudopython.builtins as builtins
import semu.pseudopython.flow as flow
import semu.pseudopython.helpers as h
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls
import semu.pseudopython.modules as mods
import semu.pseudopython.packages as pack


class Translator:
    top_level: pack.TopLevel
    settings: h.CompileSettings
    context: ns.Namespace

    def __init__(self, settings: h.CompileSettings):
        self.settings = settings
        top_level = pack.TopLevel()
        self.context = top_level
        self.top_level = top_level

    def resolve_object(self, ast_name: ast.AST) -> ns.NameLookup:
        path = h.collect_path_from_attribute(ast_name)
        top_name = path.pop(0)
        lookup = self.context.get_name(top_name)

        if lookup is None:
            raise UserWarning(f'Unknown reference {top_name}')

        while path:
            next_name = path.pop(0)

            if not isinstance(lookup.known_name, ns.Namespace):
                raise UserWarning(f'Unsupported path lookup {lookup.known_name}')

            lookup = lookup.known_name.get_name(next_name)

            if lookup is None:
                raise UserWarning(f'Unknown nested reference {next_name}')

        return lookup

    def translate_call(self, ast_call: ast.Call, target: regs.Register):
        callable = self.translate_expression(ast_call.func, regs.DEFAULT_REGISTER)

        if callable.target_type != 'callable':
            raise UserWarning(f'Unsupported callable {callable}')

        args = [
            self.translate_expression(ast_arg, regs.DEFAULT_REGISTER)
            for ast_arg in ast_call.args
        ]

        if isinstance(callable, builtins.BuiltinInline):
            call = h.create_inline(callable, args, target)
        elif isinstance(callable, calls.FunctionRef):
            call = h.make_call(callable, args, target)
        else:
            raise UserWarning(f'Unsupported call {ast_call}')

        return h.create_call_frame(call, args)

    def translate_const_assign(self, name: str, ast_value: ast.AST):
        if not isinstance(ast_value, ast.Constant):
            raise UserWarning(
                f'Only const assignments are supported for {name}'
            )

        value = h.int32const(ast_value)
        self.context.names[name] = n.Constant(self.context, name, 'int32', value)
        return el.VoidElement(f'Const {name} = {value}')

    def translate_boolop(self, source: ast.BoolOp, target: regs.Register):
        values = source.values
        args = [self.translate_expression(value, regs.DEFAULT_REGISTER) for value in values]
        return h.create_boolop(args, source.op, target)

    def translate_expression(self, source: ast.AST, target: regs.Register) -> el.Expression:
        if isinstance(source, ast.Constant):
            target_type = h.get_constant_type(source)
            value = h.get_constant_value(target_type, source)

            return el.ConstantExpression(
                target_type=target_type, value=value,
                target=target
            )

        if isinstance(source, ast.Name) or isinstance(source, ast.Attribute):
            lookup = self.resolve_object(source)
            namespace = lookup.namespace
            known_name = lookup.known_name

            if isinstance(known_name, n.Constant):
                return namespace.load_const(known_name, target)

            if isinstance(known_name, n.GlobalVariable):
                return namespace.load_variable(known_name, target)

            if isinstance(known_name, builtins.BuiltinInline):
                return known_name  # as expression

            if isinstance(known_name, calls.Function):
                return calls.FunctionRef(known_name, target)

            if isinstance(known_name, n.FormalParameter):
                assert isinstance(namespace, calls.Function)
                return namespace.load_actual(known_name, target)

            if isinstance(known_name, n.LocalVariable):
                assert isinstance(namespace, calls.Function)
                return namespace.load_variable(known_name, target)

            raise UserWarning(f'Unsupported name {source}')

        if isinstance(source, ast.BinOp):
            left = self.translate_expression(source.left, regs.REGISTERS[0])
            right = self.translate_expression(source.right, regs.REGISTERS[1])
            return h.create_binop(left, right, source.op, target)

        if isinstance(source, ast.Call):
            return self.translate_call(source, target)

        if isinstance(source, ast.UnaryOp):
            right = self.translate_expression(source.operand, regs.REGISTERS[0])
            return h.create_unary(right, source.op, target)

        if isinstance(source, ast.BoolOp):
            return self.translate_boolop(source, target)

        if isinstance(source, ast.Compare):
            left = self.translate_expression(source.left, regs.REGISTERS[0])
            ops = source.ops

            if len(source.comparators) != 1:
                raise UserWarning(
                    f'Unsupported number of comparators {len(source.comparators)}'
                )

            assert len(ops) == 1

            right = self.translate_expression(source.comparators[0], regs.REGISTERS[1])
            return h.create_compare(left, ops[0], right, target)

        raise UserWarning(f'Unsupported assignment source {source}')

    def translate_var_assign(self, target: n.KnownName, source: ast.AST):
        expression = self.translate_expression(source, regs.DEFAULT_REGISTER)
        t_type = target.target_type
        e_type = expression.target_type

        if t_type != e_type:
            raise UserWarning(
                f'Expression type mismath {e_type} in not {t_type}'
            )

        if isinstance(target, n.GlobalVariable):
            return el.GlobalVariableAssignment(target, expression)
        elif isinstance(target, n.LocalVariable):
            return calls.LocalVariableAssignment(target, expression)

        raise UserWarning(f'Unsupported assign target {target}')

    def translate_assign(self, ast_assign: ast.Assign):
        if len(ast_assign.targets) != 1:
            raise UserWarning(f'Assign expects 1 target, got {len(ast_assign.targets)}')

        ast_target = ast_assign.targets[0]
        ast_value = ast_assign.value
        lookup = self.resolve_object(ast_target)
        known_name = lookup.known_name

        if isinstance(known_name, (n.GlobalVariable, n.LocalVariable)):
            return self.translate_var_assign(known_name, ast_value)
        else:
            raise UserWarning(f'Unsupported assignment target {known_name}')

    def translate_type(self, ast_type: ast.AST):
        if not isinstance(ast_type, ast.Name):
            print(ast.dump(ast_type))
            raise UserWarning('External types are not supported')

        match ast_type.id:
            case 'int':
                return 'int32'
            case 'bool':
                return 'bool32'
            case name:
                raise UserWarning(f'Unsupported type found ({name})')

    def translate_ann_assign(self, assign: ast.AnnAssign):
        if assign.simple != 1:
            raise UserWarning('Only simple type declarations are supported')

        if not isinstance(assign.target, ast.Name):
            raise UserWarning('Unsupported type declaration')

        target_type = self.translate_type(assign.annotation)
        return self.context.create_variable(assign.target.id, target_type)

    def translate_if(self, ast_if: ast.If):
        test = self.translate_expression(ast_if.test, regs.DEFAULT_REGISTER)
        true_body = self.translate_body(ast_if.body)

        if test.target_type != 'bool32':
            raise UserWarning(f'If test must be of type bool32, got {test.target_type}')

        if ast_if.orelse:
            false_body = self.translate_body(ast_if.orelse)
        else:
            false_body = [el.VoidElement('no else')]

        return flow.If(test, true_body, false_body)

    def translate_while(self, ast_while: ast.While):
        test = self.translate_expression(ast_while.test, regs.DEFAULT_REGISTER)
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

    def translate_import_name(self, names: List[str]) -> n.KnownName | None:
        (found, module) = h.find_module(self.top_level, names.copy())

        lg.debug(f'Module lookup result: {found} ({module})')

        if found:
            # Already imported
            return None

        parent, name, ast_module = h.load_module(self.settings, self.top(), names.copy())
        current_context = self.context
        self.context = parent
        module = self.translate_module(name, ast_module)
        self.context = current_context
        return module

    def translate_import(self, ast_import: ast.Import):
        self.top_level.names.update(
            {
                child.name: child
                for child in [
                    self.translate_import_name(alias.name.split('.'))
                    for alias in ast_import.names
                ]
                if isinstance(child, n.KnownName)
            }
        )

    def translate_stmt(self, ast_element: ast.stmt) -> el.Element:
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
                    return self.translate_expression(value, regs.DEFAULT_REGISTER)
            case ast.Pass:
                return el.VoidElement('pass')
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
            case ast.Return:
                return self.translate_return(cast(ast.Return, ast_element))
            case ast.Import:
                self.translate_import(cast(ast.Import, ast_element))
                return el.VoidElement('import')

        lg.warning(f'Unsupported element {ast_element} ({type(ast_element)})')
        return el.VoidElement('unsupported')

    def translate_body(self, ast_body: Sequence[ast.stmt]) -> Sequence[el.Element]:
        return list(map(self.translate_stmt, ast_body))

    def translate_return(self, ast_return: ast.Return) -> el.Element:
        if isinstance(self.context, calls.Function):
            func = self.context
        else:
            raise UserWarning('Return statement outside a function')

        if ast_return.value:
            value = self.translate_expression(ast_return.value, regs.DEFAULT_REGISTER)
            f_type = func.target_type
            e_type = value.target_type

            if func.target_type != value.target_type:
                raise UserWarning(f'Return type mismatch {f_type} != {e_type}')

            func.returns = True
            return calls.ReturnValue(func, value)
        else:
            if func.target_type != 'unit':
                raise UserWarning('Function has no target type')

            return calls.ReturnUnit(func)

    def translate_function(self, ast_function: ast.FunctionDef):
        name = ast_function.name

        if ast_function.returns is None:
            target_type = 'unit'
        else:
            target_type = self.translate_type(ast_function.returns)

        args = []
        for ast_arg in ast_function.args.args:
            if ast_arg.annotation is None:
                raise UserWarning(f'Argument {ast_arg.arg} has no type')

            arg_name = ast_arg.arg
            arg_type = self.translate_type(ast_arg.annotation)
            args.append((arg_name, arg_type))

        lg.debug(f'Found function {name}')

        function = h.create_function(self.context, name, args, target_type)
        self.context.names[name] = function
        self.context = function
        function.body = self.translate_body(ast_function.body)
        h.validate_function(function)
        self.context = cast(ns.Namespace, function.parent)
        return function

    def translate_module(self, name: str, ast_module: ast.Module):
        module = mods.Module(name, self.context)
        self.context = module
        module.body = self.translate_body(ast_module.body)
        self.context = cast(ns.Namespace, module.parent)
        return module

    def translate(self, name: str, ast_module: ast.Module):
        module = self.translate_module(name, ast_module)
        assert isinstance(self.context, pack.TopLevel)
        self.context.names[name] = module

    def top(self) -> pack.TopLevel:
        return self.top_level


def eprint(*args: Any, **kwargs: Any):
    print(*args, file=sys.stderr, **kwargs)


Params = Dict[str, Any]


def emit(settings: h.CompileSettings, translator: Translator):
    top = translator.top()
    items = top.emit()

    if settings.verbose:
        eprint('------------------ AST -----------------------')
        eprint(json.dumps(top.json(), indent=2))

    if settings.verbose:
        for item in items:
            eprint(f'------------- SASM {item.modulename} ------------------')
            eprint(item.contents)

    return items


def compile_single_string(settings: h.CompileSettings, name: str, input: str):
    translator = Translator(settings)
    ast_tree = ast.parse(input)
    translator.translate(name, ast_tree)
    sasm = emit(settings, translator)
    return sasm


def compile_single_file(settings: h.CompileSettings, input: Path, output: Path):
    sasm = compile_single_string(settings, input.stem, input.read_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sasm[0].contents)


@click.command()
@click.pass_context
@click.option('-v', '--verbose', is_flag=True, help='sets logging level to debug')
@click.option('--pp-path', type=str, help='path to the pseudopython package')
@click.argument('input', type=Path)
@click.argument('output', type=Path, required=False)
def compile(ctx: click.Context, input: Path, output: Path | None, **params):
    ctx.ensure_object(h.CompileSettings)
    ctx.obj.update(**params)

    lg.basicConfig(level=lg.DEBUG if ctx.obj.verbose else lg.INFO)

    if not output:
        output = input.with_suffix('.sasm')

    lg.info(f'Translating {input.name} to {output.name}')
    compile_single_file(ctx.obj, input, output)


if __name__ == '__main__':
    compile()
