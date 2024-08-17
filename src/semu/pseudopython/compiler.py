import sys
from pathlib import Path
import logging as lg
from typing import Sequence, Dict, Any, List, cast
import ast
import json

import click

import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.builtins as bi
import semu.pseudopython.flow as flow
import semu.pseudopython.helpers as h
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls
import semu.pseudopython.methods as meth
import semu.pseudopython.modules as mods
import semu.pseudopython.packages as pack


# Late binding
calls.Function.factory = h.create_function
cls.Class.fun_factory = h.create_function
cls.Class.method_factory = h.create_method


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
        lookup = self.context.lookup_name_upwards(top_name)

        if lookup is None:
            raise UserWarning(f'Unknown reference {top_name}')

        while path:
            next_name = path.pop(0)

            if not isinstance(lookup.known_name, ns.Namespace):
                raise UserWarning(f'Unsupported path lookup {lookup.known_name}')

            lookup = lookup.known_name.get_own_name(next_name)

            if lookup is None:
                raise UserWarning(f'Unknown nested reference {next_name}')

        return lookup

    def tx_builtin_call(
        self, callable: bi.BuiltinInline, ast_args: List[ast.expr],
        target: regs.Register
    ):
        assert len(ast_args) <= len(regs.REGISTERS)
        args = []

        for i, ast_arg in enumerate(ast_args):
            args.append(self.tx_expression(ast_arg, regs.REGISTERS[i]))

        return h.create_inline(callable, args, target)

    def tx_call(self, ast_call: ast.Call, target: regs.Register):
        callable = self.tx_expression(ast_call.func)

        if isinstance(callable, bi.BuiltinInlineWrapper):
            return self.tx_builtin_call(callable.inline, ast_call.args, target)

        if not isinstance(callable.target_type, t.AbstractCallableType):
            raise UserWarning(f'Not callable type {callable}')

        args = [
            self.tx_expression(ast_arg)
            for ast_arg in ast_call.args
        ]

        if isinstance(callable, calls.FunctionRef):
            call = h.make_direct_call(callable, args, target)
            return h.create_call_frame(call, args)

        elif isinstance(callable, el.GlobalVariableLoad):
            call = h.make_pointer_call(callable, args, target)
            return h.create_call_frame(call, args)

        elif isinstance(callable, meth.MethodRef):
            # 'this' pointer is the first argument
            this_pointer = callable.instance_load(regs.DEFAULT_REGISTER)
            full_args = [this_pointer] + args
            call = h.make_method_call(callable, full_args, target)
            return h.create_call_frame(call, full_args)

        else:
            raise UserWarning(f'Unsupported callable {callable}')

    def tx_const_assign(self, name: str, ast_value: ast.AST):
        if not isinstance(ast_value, ast.Constant):
            raise UserWarning(
                f'Only const assignments are supported for {name}'
            )

        value = h.int32const(ast_value)
        self.context.add_name(n.Constant(self.context, name, t.Int32, value))
        return el.VoidElement(f'Const {name} = {value}')

    def tx_boolop(self, source: ast.BoolOp, target: regs.Register):
        values = source.values
        args = [self.tx_expression(value) for value in values]
        return h.create_boolop(args, source.op, target)

    def tx_phy_expression(
        self, source: ast.AST, target: regs.Register = regs.DEFAULT_REGISTER
    ) -> el.PhysicalExpression:

        expression = self.tx_expression(source, target)

        if not isinstance(expression, el.PhysicalExpression):
            raise UserWarning(f'Physical value required {expression}')

        return expression

    def tx_assign(self, ast_assign: ast.Assign):
        if len(ast_assign.targets) != 1:
            raise UserWarning(f'Assign expects 1 target, got {len(ast_assign.targets)}')

        ast_target = ast_assign.targets[0]
        ast_value = ast_assign.value
        lookup = self.resolve_object(ast_target)
        target = lookup.known_name
        expression = self.tx_phy_expression(ast_value)
        t_type = target.target_type
        e_type = expression.target_type

        if t_type == e_type:
            if isinstance(target, el.GlobalVariable):
                return el.GlobalVariableAssignment(target, expression)

            if isinstance(target, calls.LocalVariable):
                return calls.LocalVariableAssignment(target, expression)

            if isinstance(target, meth.StackPointerMember):
                return meth.StackPointerMemberAssignment(target, expression)

        raise UserWarning(f'Unsupported assign target {target.name} ({e_type} -> {t_type})')

    def tx_type(self, ast_type: ast.AST):
        pp_type = self.tx_expression(ast_type).target_type
        return pp_type

    def tx_ann_assign(self, assign: ast.AnnAssign):
        if assign.simple != 1:
            raise UserWarning('Only simple type declarations are supported')

        if not isinstance(assign.target, ast.Name):
            raise UserWarning('Unsupported type declaration')

        target_type = self.tx_type(assign.annotation)
        return self.context.create_variable(assign.target.id, target_type)

    def tx_if(self, ast_if: ast.If):
        test = self.tx_phy_expression(ast_if.test)
        true_body = self.tx_body(ast_if.body)

        if test.target_type != t.Bool32:
            raise UserWarning(f'If test must be of type bool32, got {test.target_type}')

        if ast_if.orelse:
            false_body = self.tx_body(ast_if.orelse)
        else:
            false_body = [el.VoidElement('no else')]

        return flow.If(test, true_body, false_body)

    def tx_while(self, ast_while: ast.While):
        test = self.tx_expression(ast_while.test)
        body = self.tx_body(ast_while.body)

        if not isinstance(test, el.PhysicalExpression):
            raise UserWarning(f'While test must be a physical expression, got {test}')

        if test.target_type != t.Bool32:
            raise UserWarning(f'While test must be of type bool32, got {test.target_type}')

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

    def tx_import_name(self, names: List[str]) -> n.KnownName | None:
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

        return el.VoidElement('import')

    def tx_class(self, ast_class: ast.ClassDef):
        classdef = cls.Class(ast_class.name, self.context)
        self.context.add_name(classdef)
        self.context = classdef

        for ast_statement in ast_class.body:
            if not isinstance(ast_statement, (ast.FunctionDef, ast.AnnAssign)):
                raise UserWarning(f'Unsupported class statement {ast_statement}')

            self.tx_stmt(ast_statement)

        self.context = cast(ns.Namespace, classdef.parent)
        return classdef

    def tx_return(self, ast_return: ast.Return) -> el.Element:
        if isinstance(self.context, calls.Function):
            func = self.context
        else:
            raise UserWarning('Return statement outside a function')

        if ast_return.value:
            value = self.tx_expression(ast_return.value)
            f_type = func.target_type
            e_type = value.target_type

            if f_type != e_type:
                raise UserWarning(f'Return type mismatch {f_type} != {e_type}')

            if not isinstance(value, el.PhysicalExpression):
                raise UserWarning(f'Unsupported return value {value}')

            func.returns = True
            return calls.ReturnValue(func, value)
        else:
            if func.target_type != t.Unit:
                raise UserWarning('Function has no target type')

            return calls.ReturnUnit(func)

    def tx_function(self, ast_function: ast.FunctionDef):
        name = ast_function.name

        lg.debug(f'Found function {name}')

        if ast_function.returns is None:
            target_type = t.Unit
        else:
            target_type = self.tx_type(ast_function.returns)

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

        function = self.context.create_function(name, args, decors, target_type)
        self.context = function
        assert isinstance(function, calls.Function)
        function.body = self.tx_body(ast_function.body)
        h.validate_function(function)
        self.context = cast(ns.Namespace, function.parent)
        return function

    def tx_subscript(self, source: ast.Subscript, target: regs.Register):
        available = regs.get_available([target])
        value_target = available.pop()
        slice_target = available.pop()

        value = self.tx_expression(source.value, value_target)
        slice = self.tx_expression(source.slice, slice_target)
        return h.create_subscript(value, slice, target)

    def tx_expression(
        self, source: ast.AST, target: regs.Register = regs.DEFAULT_REGISTER
    ) -> el.Expression:

        if isinstance(source, ast.Constant):
            target_type = h.get_constant_type(source)
            value = h.get_constant_value(target_type, source)
            return el.ConstantExpression(target_type, value, target)

        if isinstance(source, ast.Name) or isinstance(source, ast.Attribute):
            lookup = self.resolve_object(source)
            namespace = lookup.namespace
            known_name = lookup.known_name

            if isinstance(known_name, n.Constant):
                return namespace.load_const(known_name, target)

            if isinstance(known_name, el.GlobalVariable):
                return namespace.load_variable(known_name, target)

            if isinstance(known_name, bi.BuiltinInline):
                return bi.BuiltinInlineWrapper(known_name)

            if isinstance(known_name, meth.Method):
                raise UserWarning(f'Unsupported unqualified method {known_name} call')

            if isinstance(known_name, calls.Function):
                return calls.FunctionRef(known_name, target)

            if isinstance(known_name, calls.StackVariable):
                assert isinstance(namespace, calls.Function)
                return namespace.load_variable(known_name, target)

            if isinstance(known_name, t.DecoratorType):
                return el.DecoratorApplication(known_name)

            if isinstance(known_name, b.TargetType):
                return el.TypeWrapper(known_name)

            if isinstance(known_name, el.BuiltinMetaoperator):
                return known_name

            if isinstance(known_name, cls.GlobalInstance):
                return cls.GlobalInstanceLoad(known_name, target)

            if isinstance(known_name, meth.GlobalPointerMember):
                address = regs.get_temp([target])
                load = meth.GlobalInstancePointerLoad(known_name.instance_pointer, address)
                return cls.ClassMemberLoad(load, known_name.variable, target)

            if isinstance(known_name, meth.StackPointerMember):
                address = regs.get_temp([target])
                load = meth.StackInstancePointerLoad(known_name.instance_parameter, address)
                return cls.ClassMemberLoad(load, known_name.variable, target)

            if isinstance(known_name, meth.GlobalInstanceMethod):
                return meth.MethodRef.from_GIM(known_name, target)

            if isinstance(known_name, meth.GlobalPointerMethod):
                return meth.MethodRef.from_GPM(known_name, target)

            if isinstance(known_name, meth.StackPointerMethod):
                return meth.MethodRef.from_SPM(known_name, target)

            raise UserWarning(f'Unsupported name {known_name} as expression')

        if isinstance(source, ast.BinOp):
            left = self.tx_expression(source.left, regs.REGISTERS[0])
            right = self.tx_expression(source.right, regs.REGISTERS[1])
            return h.create_binop(left, right, source.op, target)

        if isinstance(source, ast.Call):
            return self.tx_call(source, target)

        if isinstance(source, ast.UnaryOp):
            right = self.tx_expression(source.operand, regs.REGISTERS[0])
            return h.create_unary(right, source.op, target)

        if isinstance(source, ast.BoolOp):
            return self.tx_boolop(source, target)

        if isinstance(source, ast.Compare):
            left = self.tx_expression(source.left, regs.REGISTERS[0])
            ops = source.ops

            if len(source.comparators) != 1:
                raise UserWarning(
                    f'Unsupported number of comparators {len(source.comparators)}'
                )

            assert len(ops) == 1

            right = self.tx_expression(source.comparators[0], regs.REGISTERS[1])
            return h.create_compare(left, ops[0], right, target)

        if isinstance(source, ast.Subscript):
            return self.tx_subscript(source, target)

        if isinstance(source, (ast.Tuple, ast.List)):
            return el.List(list(self.tx_expression(e) for e in source.elts))

        raise UserWarning(f'Unsupported expression {source}')

    def tx_stmt(self, ast_element: ast.stmt) -> el.Element:
        lg.debug(f'Stmt {type(ast_element)}')

        match type(ast_element):
            case ast.Expr:
                value = cast(ast.Expr, ast_element).value

                if isinstance(value, ast.Compare):
                    # NB: This is a hack to support `is` as a free operator
                    return self.tx_free_is(value)
                else:
                    return self.tx_phy_expression(value)
            case ast.Pass:
                return el.VoidElement('pass')
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
        return el.VoidElement('unsupported')

    def tx_body(self, ast_body: Sequence[ast.stmt]) -> el.Elements:
        return cast(el.Elements, list(filter(
            lambda x: isinstance(x, el.Element),
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

    if settings.verbose:
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
    compile_file(ctx.obj, input, output)


if __name__ == '__main__':
    compile()
