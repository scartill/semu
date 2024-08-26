import ast
import logging as lg
from typing import cast, Type

from semu.common.hwconf import WORD_SIZE

import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.expressions as ex
import semu.pseudopython.intops as intops
import semu.pseudopython.calls as calls
import semu.pseudopython.boolops as boolops
import semu.pseudopython.cmpops as cmpops
import semu.pseudopython.namespaces as ns
import semu.pseudopython.classes as cls
import semu.pseudopython.builtins as bi
import semu.pseudopython.pointers as ptrs
import semu.pseudopython.methods as meth
import semu.pseudopython.arrays as arr
import semu.pseudopython.helpers as h


def create_binop(
    left: ex.Expression, right: ex.Expression, op: ast.AST,
    target: regs.Register
):
    if not isinstance(left, ex.PhyExpression):
        raise UserWarning(f'Unsupported binop left {left}')

    if not isinstance(right, ex.PhyExpression):
        raise UserWarning(f'Unsupported binop right {right}')

    required_type: b.PPType | None = None
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

    if left.pp_type != right.pp_type:
        raise UserWarning(f'Type mismatch {left.pp_type} != {right.pp_type}')

    pp_type = left.pp_type

    if pp_type != required_type:
        raise UserWarning(f'Unsupported binop type {pp_type}')

    return Op(pp_type, left, right, target)


def create_unary(right: ex.Expression, op: ast.AST, target: regs.Register):
    if not isinstance(right, ex.PhyExpression):
        raise UserWarning(f'Unsupported unary right {right}')

    required_type: b.PPType | None = None
    Op = None

    if isinstance(op, ast.Not):
        required_type = t.Bool32
        Op = boolops.Not

    if isinstance(op, ast.USub):
        required_type = t.Int32
        Op = intops.Neg

    if Op is None:
        raise UserWarning(f'Unsupported unary op {op}')

    pp_type = right.pp_type

    if pp_type != required_type:
        raise UserWarning(f'Unsupported binop type {pp_type}')

    return Op(pp_type, right, target)


def create_boolop(args: ex.Expressions, op: ast.AST, target: regs.Register):
    pp_type: b.PPType = t.Bool32

    for arg in args:
        if not isinstance(arg, ex.PhyExpression):
            raise UserWarning(f'Unsupported boolop arg {arg}')

        if arg.pp_type != t.Bool32:
            raise UserWarning(f'Unsupported boolop type {arg.pp_type}')

    if isinstance(op, ast.And):
        return boolops.And(pp_type, cast(ex.PhyExpressions, args), target)

    if isinstance(op, ast.Or):
        return boolops.Or(pp_type, cast(ex.PhyExpressions, args), target)

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
    left: ex.Expression, ast_op: ast.AST, right: ex.Expression,
    target: regs.Register
):
    if not isinstance(left, ex.PhyExpression):
        raise UserWarning(f'Unsupported compare left {left}')

    if not isinstance(right, ex.PhyExpression):
        raise UserWarning(f'Unsupported compare right {right}')

    operand_type = left.pp_type

    if right.pp_type != operand_type:
        raise UserWarning(f'Unsupported compare type {right.pp_type}')

    Op = COMPARE_OPS.get(type(ast_op))  # type: ignore

    if Op is None:
        raise UserWarning(f'Unsupported compare op {ast_op}')

    return cmpops.Compare(target, left, Op(), right)


def create_callable(
    Cls: Type[h.TFunction],
    context: ns.Namespace, name: str, args: ns.ArgDefs,
    decors: ex.Expressions, pp_type: b.PPType
) -> h.TFunction:

    function = Cls(name, context, pp_type)

    for d in decors:
        if not isinstance(d, ex.DecoratorApplication):
            raise UserWarning('Unsupported decorator type {d}')

        function.add_decorator(d)

    total = len(args)

    for inx, (arg_name, arg_type) in enumerate(args):
        # NB: Note that the offset skips the return address and saved frame pointer
        offset = -(total - inx + 2) * WORD_SIZE
        lg.debug(f'Adding formal {arg_name} at {offset} of type {arg_type}')

        if isinstance(arg_type, cls.InstancePointerType):
            lg.debug(f'Adding instance formal {arg_name} at {offset} of type {arg_type}')
            formal = meth.InstanceFormalParameter(function, arg_name, offset, arg_type)
        elif isinstance(arg_type, t.PhysicalType):
            lg.debug(f'Adding physical formal {arg_name} at {offset} of type {arg_type}')
            formal = calls.FormalParameter(function, arg_name, offset, arg_type)
        else:
            raise UserWarning(f'Unsupported formal type {arg_type}')

        function.add_name(formal)

    return function


def create_function(
    context: ns.Namespace, name: str, args: ns.ArgDefs,
    decors: ex.Expressions, pp_type: b.PPType
) -> calls.Function:

    return create_callable(calls.Function, context, name, args, decors, pp_type)


def create_method(
    context: ns.Namespace, name: str, args: ns.ArgDefs,
    decors: ex.Expressions, pp_type: b.PPType
) -> meth.Method:

    return create_callable(meth.Method, context, name, args, decors, pp_type)


def create_inline(inline: bi.BuiltinInline, args: ex.Expressions, target: regs.Register):
    return inline.factory(args, target)


def create_call_frame(call: ex.Expression, args: ex.Expressions):
    if not isinstance(call, ex.PhyExpression):
        raise UserWarning(f'Unsupported call target {call}')

    for arg in args:
        if not isinstance(arg, ex.PhyExpression):
            raise UserWarning(f'Unsupported call arg {arg}')

    actuals = [
        calls.ActualParameter(inx, cast(ex.PhyExpression, arg))
        for inx, arg in enumerate(args)
    ]

    return calls.CallFrame(call.pp_type, actuals, call, call.target)


def create_global_variable(
    parent: ns.Namespace, name: str, pp_type: b.PPType
) -> arr.Globals:

    if isinstance(pp_type, cls.Class):
        lg.debug(f'Creating a global instance {name} of {pp_type}')
        instance = cls.GlobalInstance(parent, name, pp_type)

        members = [
            cls.ClassMember(instance, classvar)
            for classvar in pp_type.names.values()
            if isinstance(classvar, cls.ClassVariable)
        ]

        instance.members = members
        return instance

    if isinstance(pp_type, cls.InstancePointerType):
        lg.debug(f'Creating a global instance pointer {name} of {pp_type}')
        return meth.GlobalInstancePointer(parent, name, pp_type)

    if isinstance(pp_type, arr.ArrayType):
        lg.debug(f'Creating a global array {name}')

        items = [
            create_global_variable(parent, f'{name}_{inx}', pp_type.item_type)
            for inx in range(pp_type.length)
        ]

        return arr.GlobalArray(parent, name, pp_type, items)

    if not isinstance(pp_type, t.PhysicalType):
        raise UserWarning(f'Type {name} must be representable')

    lg.debug(f'Creating a global variable {name}')
    create = ex.GlobalVariable(parent, name, pp_type)
    return create


def create_ptr_type(slice: ex.Expression):
    if isinstance(slice.pp_type, cls.InstancePointerType):
        return ex.TypeWrapper(cls.InstancePointerType(slice.pp_type.ref_type))

    if isinstance(slice.pp_type, cls.Class):
        return ex.TypeWrapper(cls.InstancePointerType(slice.pp_type))

    if isinstance(slice.pp_type, t.PhysicalType):
        return ex.TypeWrapper(t.PointerType(slice.pp_type))

    raise UserWarning(f'Unsupported pointer type {slice.pp_type}')


def create_funptr_type(slice: ex.Expression):
    if not isinstance(slice, ex.MetaList):
        raise UserWarning('Unsupported function pointer type')

    if len(slice.elements) != 2:
        raise UserWarning('Unsupported function pointer type (length is not 2)')

    param_types = slice.elements[0]
    return_type = slice.elements[1]
    (arg_types, return_type) = h.funptr_validate(param_types, return_type)
    return ex.TypeWrapper(ptrs.FunctionPointerType(arg_types, return_type))


def create_methptr_type(slice: ex.Expression):
    if not isinstance(slice, ex.MetaList):
        raise UserWarning('Unsupported method pointer type')

    if len(slice.elements) != 3:
        raise UserWarning('Unsupported method pointer type (length is not 3)')

    class_type_expr = slice.elements[0]
    param_type_expr = slice.elements[1]
    return_type_expr = slice.elements[2]

    if not isinstance(class_type_expr, ex.TypeWrapper):
        raise UserWarning('Unsupported method pointer type (class type is not a type)')

    if not isinstance(class_type_expr.pp_type, cls.Class):
        raise UserWarning('Unsupported method pointer type (class type is not a class)')

    class_type = class_type_expr.pp_type
    (arg_types, return_type) = h.funptr_validate(param_type_expr, return_type_expr)
    this_type = cls.InstancePointerType(class_type)
    full_arg_types = [this_type] + arg_types
    return ex.TypeWrapper(meth.MethodPointerType(class_type, full_arg_types, return_type))


def create_array_type(slice: ex.Expression):
    if not isinstance(slice, ex.MetaList):
        raise UserWarning('Malformed array type definition')

    if len(slice.elements) != 2:
        raise UserWarning('Unsupported array type definition')

    item_type_expr = slice.elements[0]
    len_expr = slice.elements[1]

    if not isinstance(item_type_expr, ex.TypeWrapper):
        raise UserWarning('Unsupported item type (item type is not a type)')

    item_type = item_type_expr.pp_type

    if not isinstance(item_type, t.PhysicalType):
        raise UserWarning(f'Item type must be representable {item_type}')

    if not isinstance(len_expr, ex.ConstantExpression):
        raise UserWarning('Array length must be a constant')

    value = len_expr.value

    if not isinstance(value, int):
        raise UserWarning('Array length must be an integer constant')

    if value <= 0:
        raise UserWarning('Array length must be integer')

    array_type = arr.ArrayType(item_type, value)
    return ex.TypeWrapper(array_type)


def create_subscript(value: ex.Expression, slice: ex.Expression, target):
    match value:
        case ptrs.PointerOperator:
            return create_ptr_type(slice)
        case ptrs.FunctionPointerOperator:
            return create_funptr_type(slice)
        case ptrs.MethodPointerOperator:
            return create_methptr_type(slice)
        case arr.ArrayOperator:
            return create_array_type(slice)
        case _:
            raise UserWarning(f'Unsupported subscript slice type {slice.pp_type}')


def make_direct_call(
    func_ref: calls.FunctionRef, args: ex.Expressions, target: regs.Register
):
    lg.debug(f'Direct call to {func_ref.func.name}')
    c_type = func_ref.func.callable_type()
    h.validate_call(c_type.arg_types, args)
    return calls.FunctionCall(func_ref, c_type.return_type, target)


def make_pointer_call(
    pointer: ex.Expression, args: ex.Expressions, target: regs.Register
):
    callable_pointers = (ptrs.FunctionPointerType, meth.MethodPointerType)

    if not isinstance(pointer.pp_type, callable_pointers):
        raise UserWarning(f'Unsupported pointer type {pointer.pp_type}')

    if not isinstance(pointer, ex.PhyExpression):
        raise UserWarning(f'Unrepresentable function pointer {pointer}')

    t_type = pointer.pp_type
    lg.debug(f'Indirect call to function {t_type}')
    h.validate_call(t_type.arg_types, args)
    return calls.FunctionCall(pointer, t_type.return_type, target)


def make_method_call(
    m_ref: ex.PhyExpression, callable_type: meth.MethodPointerType,
    args: ex.Expressions, target: regs.Register
):
    lg.debug(f'Direct method call to {m_ref.pp_type}')
    h.validate_call(callable_type.arg_types, args)
    return meth.MethodCall(m_ref, callable_type.return_type, target)


def make_bound_method_call(
    bound_ref: meth.BoundMethodRef, args: ex.Expressions, target: regs.Register
):
    this = bound_ref.instance_load
    ref = bound_ref.method_load

    for arg in args:
        if not isinstance(arg, ex.PhyExpression):
            raise UserWarning(f'Unsupported bound method call arg {arg}')

    # 'this' pointer is the first argument
    full_args = [this]
    full_args.extend(cast(ex.PhyExpressions, args))
    call = make_method_call(ref, bound_ref.callable_type, full_args, target)
    return create_call_frame(call, full_args)
