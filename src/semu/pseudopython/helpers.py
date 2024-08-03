import ast
import logging as lg

from semu.pseudopython.elements import (
    Register, TargetType,
    Expression, Expressions
)

import semu.pseudopython.intops as intops
import semu.pseudopython.boolops as boolops
import semu.pseudopython.cmpops as cmpops
import semu.pseudopython.namespaces as ns


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


def get_constant_value(target_type: TargetType, source: ast.AST):
    if target_type == 'int32':
        return int32const(source)

    if target_type == 'bool32':
        return bool32const(source)

    raise UserWarning(f'Unsupported constant type {target_type}')


def create_binop(left: Expression, right: Expression, op: ast.AST, target: Register):
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


def create_unary(right: Expression, op: ast.AST, target: Register):
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


def create_boolop(args: Expressions, op: ast.AST, target: Register):
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


def create_compare(left: Expression, ast_op: ast.AST, right: Expression, target: Register):
    operand_type = left.target_type

    if right.target_type != operand_type:
        raise UserWarning(f'Unsupported compare type {right.target_type}')

    Op = COMPARE_OPS.get(type(ast_op))  # type: ignore

    if Op is None:
        raise UserWarning(f'Unsupported compare op {ast_op}')

    lg.debug(f'Creating compare {ast_op} {left} {right}')

    return cmpops.Compare(target, left, Op(), right)


def create_function(
    context: ns.Namespace, name: str,
    args: ast.arguments, target_type: TargetType
) -> ns.Function:
    function = ns.Function(name, 'unit', context)

    for ast_arg in args.args:
        raise NotImplementedError()

    function.args = []
    return function


def make_call(known_name: ns.KnownName, args: Expressions, target: Register):
    if not isinstance(known_name, ns.Function):
        raise UserWarning(f'{known_name.name} is not callable')
