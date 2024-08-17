from dataclasses import dataclass
import ast
import logging as lg
from typing import List, cast, Type, TypeVar
from pathlib import Path

from semu.common.hwconf import WORD_SIZE

import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el
import semu.pseudopython.intops as intops
import semu.pseudopython.calls as calls
import semu.pseudopython.boolops as boolops
import semu.pseudopython.cmpops as cmpops
import semu.pseudopython.namespaces as ns
import semu.pseudopython.classes as cls
import semu.pseudopython.builtins as bi
import semu.pseudopython.modules as mods
import semu.pseudopython.packages as pack
import semu.pseudopython.pointers as ptrs


@dataclass
class CompileSettings:
    verbose: bool
    pp_path: str

    def __init__(self):
        self.verbose = False
        self.pp_path = ''

    def update(self, verbose: bool | None = None, pp_path: str | None = None):
        if verbose is not None:
            self.verbose = verbose

        if pp_path is not None:
            self.pp_path = pp_path

        return self


def get_constant_type(ast_const: ast.Constant):
    if isinstance(ast_const.value, bool):
        return t.Bool32

    if isinstance(ast_const.value, int):
        return t.Int32

    raise UserWarning(f'Unsupported constant type {ast_const.value}')


def int32const(ast_value: ast.AST):
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


def get_constant_value(target_type: b.TargetType, source: ast.AST):
    if target_type == t.Int32:
        return int32const(source)

    if target_type == t.Bool32:
        return bool32const(source)

    raise UserWarning(f'Unsupported constant type {target_type}')


def create_binop(
    left: el.Expression, right: el.Expression, op: ast.AST,
    target: regs.Register
):
    if not isinstance(left, el.PhysicalExpression):
        raise UserWarning(f'Unsupported binop left {left}')

    if not isinstance(right, el.PhysicalExpression):
        raise UserWarning(f'Unsupported binop right {right}')

    required_type: b.TargetType | None = None
    Op = None

    if isinstance(op, ast.Add):
        required_type = t.Int32
        Op = intops.Add

    if isinstance(op, ast.Sub):
        required_type = t.Int32
        Op = intops.Sub

    if isinstance(op, ast.Mult):
        required_type = t.Int32
        Op = intops.Mul

    if Op is None:
        raise UserWarning(f'Unsupported binop {op}')

    if left.target_type != right.target_type:
        raise UserWarning(f'Type mismatch {left.target_type} != {right.target_type}')

    target_type = left.target_type

    if target_type != required_type:
        raise UserWarning(f'Unsupported binop type {target_type}')

    return Op(target_type, target, left, right)


def create_unary(right: el.Expression, op: ast.AST, target: regs.Register):
    if not isinstance(right, el.PhysicalExpression):
        raise UserWarning(f'Unsupported unary right {right}')

    required_type: b.TargetType | None = None
    Op = None

    if isinstance(op, ast.Not):
        required_type = t.Bool32
        Op = boolops.Not

    if isinstance(op, ast.USub):
        required_type = t.Int32
        Op = intops.Neg

    if Op is None:
        raise UserWarning(f'Unsupported unary op {op}')

    target_type = right.target_type

    if target_type != required_type:
        raise UserWarning(f'Unsupported binop type {target_type}')

    return Op(target_type, target, right)


def create_boolop(args: el.Expressions, op: ast.AST, target: regs.Register):
    target_type: b.TargetType = t.Bool32

    for arg in args:
        if not isinstance(arg, el.PhysicalExpression):
            raise UserWarning(f'Unsupported boolop arg {arg}')

        if arg.target_type != t.Bool32:
            raise UserWarning(f'Unsupported boolop type {arg.target_type}')

    if isinstance(op, ast.And):
        return boolops.And(target_type, target, cast(el.PhysicalExpressions, args))

    if isinstance(op, ast.Or):
        return boolops.Or(target_type, target, cast(el.PhysicalExpressions, args))

    raise UserWarning(f'Unsupported boolop {op}')


COMPARE_OPS = {
    ast.Eq: cmpops.Eq,
    ast.NotEq: cmpops.NotEq,
    ast.Lt: cmpops.Lt,
    ast.LtE: cmpops.LtE,
    ast.Gt: cmpops.Gt,
    ast.GtE: cmpops.GtE
}


def create_compare(
    left: el.Expression, ast_op: ast.AST, right: el.Expression,
    target: regs.Register
):
    if not isinstance(left, el.PhysicalExpression):
        raise UserWarning(f'Unsupported compare left {left}')

    if not isinstance(right, el.PhysicalExpression):
        raise UserWarning(f'Unsupported compare right {right}')

    operand_type = left.target_type

    if right.target_type != operand_type:
        raise UserWarning(f'Unsupported compare type {right.target_type}')

    Op = COMPARE_OPS.get(type(ast_op))  # type: ignore

    if Op is None:
        raise UserWarning(f'Unsupported compare op {ast_op}')

    return cmpops.Compare(target, left, Op(), right)


TFunction = TypeVar('TFunction', calls.Function, calls.Method)


def create_callable(
    Cls: Type[TFunction],
    context: ns.Namespace, name: str, args: ns.ArgDefs,
    decors: el.Expressions, target_type: b.TargetType
) -> TFunction:

    function = Cls(name, context, target_type)

    for d in decors:
        if not isinstance(d, el.DecoratorApplication):
            raise UserWarning('Unsupported decorator type {d}')

        function.add_decorator(d)

    total = len(args)

    for inx, (arg_name, arg_type) in enumerate(args):
        # NB: Note that the offset skips the return address and saved frame pointer
        offset = -(total - inx + 2) * WORD_SIZE
        lg.debug(f'Adding formal {arg_name} at {offset} of type {arg_type}')

        if isinstance(arg_type, t.PhysicalType):
            lg.debug(f'Adding physical formal {arg_name} at {offset} of type {arg_type}')
            formal = calls.SimpleFormalParameter(function, arg_name, offset, arg_type)
        elif isinstance(arg_type, cls.InstancePointerType):
            lg.debug(f'Adding instance formal {arg_name} at {offset} of type {arg_type}')
            formal = calls.InstanceFormalParameter(function, arg_name, offset, arg_type)
        else:
            raise UserWarning(f'Unsupported formal type {arg_type}')

        function.add_name(formal)

    return function


def create_function(
    context: ns.Namespace, name: str, args: ns.ArgDefs,
    decors: el.Expressions, target_type: b.TargetType
) -> calls.Function:

    return create_callable(calls.Function, context, name, args, decors, target_type)


def create_method(
    context: ns.Namespace, name: str, args: ns.ArgDefs,
    decors: el.Expressions, target_type: b.TargetType
) -> calls.Method:

    return create_callable(calls.Method, context, name, args, decors, target_type)


def validate_function(func: calls.Function):
    if func.target_type != t.Unit and not func.returns:
        raise UserWarning(f'Function {func.name} does not return')


def create_inline(inline: bi.BuiltinInline, args: el.Expressions, target: regs.Register):
    return inline.factory(args, target)


def validate_call(func: calls.Function, args: el.Expressions):
    f_name = func.name

    lg.debug(f'Making call to {f_name}')

    formal_args = func.formals()

    if len(formal_args) != len(args):
        raise UserWarning(
            f'Function: {f_name} :: '
            f'Argument count mismatch: need {len(formal_args)}, got {len(args)}'
        )

    for formal_arg, arg in zip(formal_args, args):
        if formal_arg.target_type != arg.target_type:
            raise UserWarning(
                f'Argument type mismatch {formal_arg.target_type} != {arg.target_type}'
            )


def make_call(func_ref: calls.FunctionRef, args: el.Expressions, target: regs.Register):
    validate_call(func_ref.func, args)
    return calls.FunctionCall(func_ref, target)


def make_method_call(m_ref: calls.MethodRef, args: el.Expressions, target: regs.Register):
    validate_call(m_ref.instance_method.method, args)
    return calls.MethodCall(m_ref, target)


def create_call_frame(call: el.Expression, args: el.Expressions):
    if not isinstance(call, el.PhysicalExpression):
        raise UserWarning(f'Unsupported call target {call}')

    for arg in args:
        if not isinstance(arg, el.PhysicalExpression):
            raise UserWarning(f'Unsupported call arg {arg}')

    actuals = [
        calls.ActualParameter(inx, cast(el.PhysicalExpression, arg))
        for inx, arg in enumerate(args)
    ]

    return calls.CallFrame(call.target_type, call.target, actuals, call)


def collect_path_from_attribute(ast_attr: ast.AST) -> List[str]:
    path = []

    cursor = ast_attr

    while isinstance(cursor, ast.Attribute):
        path.append(cursor.attr)
        cursor = cursor.value

    if not isinstance(cursor, ast.Name):
        raise UserWarning(f'Unsupported attribute path {cursor}')

    path.append(cursor.id)
    path.reverse()
    return path


def find_module(namespace: ns.Namespace, names: List[str]):
    name = names.pop(0)
    lookup = namespace.lookup_name_upwards(name)

    if not lookup:
        return (False, namespace, name, names)

    known_name = lookup.known_name

    if not isinstance(known_name, ns.Namespace):
        raise UserWarning(f'Expected package or module {name}')

    if names:
        return find_module(known_name, names)

    if not isinstance(known_name, mods.Module):
        raise UserWarning(f'Expected module {name}')

    return (True, known_name, name, names)


def locate_first_package(settings: CompileSettings, name: str) -> Path:
    found_path = None

    for pp_path_part in settings.pp_path.split(';'):
        path = Path(pp_path_part) / name

        if path.exists() or path.with_suffix('.py').exists():
            if found_path is not None:
                raise UserWarning(f'Multiple paths found for {name}')

            found_path = path

    if found_path is None:
        raise UserWarning(f'Package {name} not found')

    lg.debug(f'Located first package {name} at {found_path}')

    return found_path


def load_module(settings: CompileSettings, parent: ns.Namespace, name: str, names: List[str]):
    if isinstance(parent, pack.TopLevel):
        head = locate_first_package(settings, name)
    else:
        assert isinstance(parent, pack.Package)
        head = parent.path / name

    while names:
        lg.debug(f'Creating package {name} from {head}')
        package = pack.Package(name, parent, head)
        parent.add_name(package)
        parent = package
        name = names.pop(0)
        head = head / name

        if names and head.exists():
            continue

        if not names and head.with_suffix('.py').exists():
            break

    if head.with_suffix('.py').exists():
        lg.debug(f'Loading new module {name} from {head}')
        return (parent, name, ast.parse(head.with_suffix('.py').read_text()))
    else:
        raise UserWarning(f'No module found for {name}')


def create_global_variable(
    parent: ns.Namespace, name: str, target_type: b.TargetType
) -> el.GlobalVariable | cls.GlobalInstance:

    if isinstance(target_type, cls.Class):
        lg.debug(f'Creating a global instance {name} of {target_type.name}')
        instance = cls.GlobalInstance(parent, name, target_type)

        is_classvar = lambda x: isinstance(x, cls.ClassVariable)

        for classvar in filter(is_classvar, target_type.names.values()):
            instance.add_name(
                create_global_variable(instance, classvar.name, classvar.target_type)
            )

        is_method = lambda x: isinstance(x, calls.Method)

        for method in filter(is_method, target_type.names.values()):

            method = calls.GlobalInstanceMethod(
                instance,
                cast(calls.Method, method)
            )

            instance.add_name(method)

        return instance

    if isinstance(target_type, cls.InstancePointerType):
        return cls.GlobalInstancePointer(parent, name, target_type)
    else:
        if not isinstance(target_type, t.PhysicalType):
            raise UserWarning(f'Type {name} must be representable')

        lg.debug(f'Creating a global variable {name}')
        create = el.GlobalVariable(parent, name, target_type)
        return create


def create_subscript(value: el.Expression, slice: el.Expression, target):
    if value != ptrs.PointerOperator:
        raise UserWarning(f'Unsupported subscript value type {value}')

    if isinstance(slice.target_type, cls.Class):
        return el.TypeWrapper(cls.InstancePointerType(slice.target_type))

    if isinstance(slice.target_type, t.PhysicalType):
        return el.TypeWrapper(t.PointerType(slice.target_type))

    raise UserWarning(f'Unsupported subscript slice type {slice.target_type}')
