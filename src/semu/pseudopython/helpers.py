from dataclasses import dataclass
import ast
import logging as lg
from typing import List
from pathlib import Path

import semu.pseudopython.registers as regs
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.intops as intops
import semu.pseudopython.boolops as boolops
import semu.pseudopython.cmpops as cmpops
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls
import semu.pseudopython.builtins as bi
import semu.pseudopython.modules as mods
import semu.pseudopython.packages as pack


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
        return 'bool32'

    if isinstance(ast_const.value, int):
        return 'int32'

    raise UserWarning(f'Unsupported constant type {type(ast_const.value)}')


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


def get_constant_value(target_type: n.TargetType, source: ast.AST):
    if target_type == 'int32':
        return int32const(source)

    if target_type == 'bool32':
        return bool32const(source)

    raise UserWarning(f'Unsupported constant type {target_type}')


def create_binop(left: el.Expression, right: el.Expression, op: ast.AST, target: regs.Register):
    required_type = None
    Op = None

    if isinstance(op, ast.Add):
        required_type = 'int32'
        Op = intops.Add

    if isinstance(op, ast.Sub):
        required_type = 'int32'
        Op = intops.Sub

    if isinstance(op, ast.Mult):
        required_type = 'int32'
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
    required_type = None
    Op = None

    if isinstance(op, ast.Not):
        required_type = 'bool32'
        Op = boolops.Not

    if isinstance(op, ast.USub):
        required_type = 'int32'
        Op = intops.Neg

    if Op is None:
        raise UserWarning(f'Unsupported unary op {op}')

    target_type = right.target_type

    if target_type != required_type:
        raise UserWarning(f'Unsupported binop type {target_type}')

    return Op(target_type, target, right)


def create_boolop(args: el.Expressions, op: ast.AST, target: regs.Register):
    target_type = 'bool32'

    for arg in args:
        if arg.target_type != 'bool32':
            raise UserWarning(f'Unsupported boolop type {arg.target_type}')

    if isinstance(op, ast.And):
        return boolops.And(target_type, target, args)

    if isinstance(op, ast.Or):
        return boolops.Or(target_type, target, args)

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
    operand_type = left.target_type

    if right.target_type != operand_type:
        raise UserWarning(f'Unsupported compare type {right.target_type}')

    Op = COMPARE_OPS.get(type(ast_op))  # type: ignore

    if Op is None:
        raise UserWarning(f'Unsupported compare op {ast_op}')

    return cmpops.Compare(target, left, Op(), right)


def create_function(
    context: ns.Namespace, name: str, args: calls.ArgDefs, target_type: n.TargetType
) -> calls.Function:
    return calls.Function(name, context, args, target_type)


def validate_function(func: calls.Function):
    if func.target_type != 'unit' and not func.returns:
        raise UserWarning(f'Function {func.name} does not return')


def create_inline(inline: bi.BuiltinInline, args: el.Expressions, target: regs.Register):
    return inline.factory(inline.return_type, args, target)


def make_call(func_ref: calls.FunctionRef, args: el.Expressions, target: regs.Register):
    f_name = func_ref.func.name
    f_type = func_ref.func.target_type

    lg.debug(f'Making call to {f_name}({args}) -> {f_type}')

    formal_args = func_ref.func.formals()

    if len(formal_args) != len(args):
        raise UserWarning(f'Argument count mismatch {len(formal_args)} != {len(args)}')

    for formal_arg, arg in zip(formal_args, args):
        if formal_arg.target_type != arg.target_type:
            raise UserWarning(
                f'Argument type mismatch {formal_arg.target_type} != {arg.target_type}'
            )

    return calls.FunctionCall(f_type, target, func_ref)


def create_call_frame(call: el.Expression, args: el.Expressions):
    actuals = [
        calls.ActualParameter(inx, arg)
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
    lookup = namespace.get_name(name)

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
        parent.names[name] = package
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
