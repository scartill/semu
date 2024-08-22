import ast
import logging as lg
from typing import List, cast, Type, TypeVar
from pathlib import Path

from semu.common.hwconf import WORD_SIZE

import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el
import semu.pseudopython.names as n
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
import semu.pseudopython.methods as meth
import semu.pseudopython.arrays as arr


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
    if not isinstance(left, el.PhyExpression):
        raise UserWarning(f'Unsupported binop left {left}')

    if not isinstance(right, el.PhyExpression):
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

    return Op(target_type, left, right, target)


def create_unary(right: el.Expression, op: ast.AST, target: regs.Register):
    if not isinstance(right, el.PhyExpression):
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

    return Op(target_type, right, target)


def create_boolop(args: el.Expressions, op: ast.AST, target: regs.Register):
    target_type: b.TargetType = t.Bool32

    for arg in args:
        if not isinstance(arg, el.PhyExpression):
            raise UserWarning(f'Unsupported boolop arg {arg}')

        if arg.target_type != t.Bool32:
            raise UserWarning(f'Unsupported boolop type {arg.target_type}')

    if isinstance(op, ast.And):
        return boolops.And(target_type, cast(el.PhyExpressions, args), target)

    if isinstance(op, ast.Or):
        return boolops.Or(target_type, cast(el.PhyExpressions, args), target)

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
    if not isinstance(left, el.PhyExpression):
        raise UserWarning(f'Unsupported compare left {left}')

    if not isinstance(right, el.PhyExpression):
        raise UserWarning(f'Unsupported compare right {right}')

    operand_type = left.target_type

    if right.target_type != operand_type:
        raise UserWarning(f'Unsupported compare type {right.target_type}')

    Op = COMPARE_OPS.get(type(ast_op))  # type: ignore

    if Op is None:
        raise UserWarning(f'Unsupported compare op {ast_op}')

    return cmpops.Compare(target, left, Op(), right)


TFunction = TypeVar('TFunction', calls.Function, meth.Method)


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

        if isinstance(arg_type, cls.InstancePointerType):
            lg.debug(f'Adding instance formal {arg_name} at {offset} of type {arg_type}')
            formal = meth.InstanceFormalParameter(function, arg_name, offset, arg_type)
        elif isinstance(arg_type, t.PhysicalType):
            lg.debug(f'Adding physical formal {arg_name} at {offset} of type {arg_type}')
            formal = calls.SimpleFormalParameter(function, arg_name, offset, arg_type)
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
) -> meth.Method:

    return create_callable(meth.Method, context, name, args, decors, target_type)


def validate_function(func: calls.Function):
    if func.return_type != t.Unit and not func.returns:
        raise UserWarning(f'Function {func.name} does not return')


def create_inline(inline: bi.BuiltinInline, args: el.Expressions, target: regs.Register):
    return inline.factory(args, target)


def validate_call(arg_types: t.PhysicalTypes, args: el.Expressions):
    if len(arg_types) != len(args):
        raise UserWarning(
            f'Argument count mismatch: need {len(arg_types)}, got {len(args)}'
        )

    for arg_type, arg in zip(arg_types, args):
        if arg_type != arg.target_type:
            raise UserWarning(
                f'Argument type mismatch {arg_type} != {arg.target_type}'
            )


def make_direct_call(
    func_ref: calls.FunctionRef, args: el.Expressions, target: regs.Register
):
    lg.debug(f'Direct call to {func_ref.func.name}')
    c_type = func_ref.func.callable_type()
    validate_call(c_type.arg_types, args)
    return calls.FunctionCall(func_ref, c_type.return_type, target)


def make_pointer_call(
    pointer: el.Expression, args: el.Expressions, target: regs.Register
):
    callable_pointers = (ptrs.FunctionPointerType, meth.MethodPointerType)

    if not isinstance(pointer.target_type, callable_pointers):
        raise UserWarning(f'Unsupported pointer type {pointer.target_type}')

    if not isinstance(pointer, el.PhyExpression):
        raise UserWarning(f'Unrepresentable function pointer {pointer}')

    t_type = pointer.target_type
    lg.debug(f'Indirect call to function {t_type}')
    validate_call(t_type.arg_types, args)
    return calls.FunctionCall(pointer, t_type.return_type, target)


def make_method_call(
    m_ref: el.PhyExpression, callable_type: meth.MethodPointerType,
    args: el.Expressions, target: regs.Register
):
    lg.debug(f'Direct method call to {m_ref.target_type}')
    validate_call(callable_type.arg_types, args)
    return meth.MethodCall(m_ref, callable_type.return_type, target)


def create_call_frame(call: el.Expression, args: el.Expressions):
    if not isinstance(call, el.PhyExpression):
        raise UserWarning(f'Unsupported call target {call}')

    for arg in args:
        if not isinstance(arg, el.PhyExpression):
            raise UserWarning(f'Unsupported call arg {arg}')

    actuals = [
        calls.ActualParameter(inx, cast(el.PhyExpression, arg))
        for inx, arg in enumerate(args)
    ]

    return calls.CallFrame(call.target_type, actuals, call, call.target)


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
) -> arr.Globals:

    if isinstance(target_type, cls.Class):
        lg.debug(f'Creating a global instance {name} of {target_type.name}')
        instance = cls.GlobalInstance(parent, name, target_type)

        is_classvar = lambda x: isinstance(x, cls.ClassVariable)

        for classvar in filter(is_classvar, target_type.names.values()):
            if not isinstance(classvar.target_type, t.PhysicalType):
                raise UserWarning(f'Unsupported class variable {classvar.target_type}')

            member_type = classvar.target_type
            instance.add_name(create_global_variable(instance, classvar.name, member_type))

        is_method = lambda x: isinstance(x, meth.Method)

        for method in filter(is_method, target_type.names.values()):

            method = meth.GlobalInstanceMethod(
                instance,
                cast(meth.Method, method)
            )

            instance.add_name(method)

        return instance

    if isinstance(target_type, cls.InstancePointerType):
        print('GLOBAL INSTANCE POINTER', name, target_type)
        return meth.GlobalInstancePointer(parent, name, target_type)

    if isinstance(target_type, arr.ArrayType):
        lg.debug(f'Creating a global array {name}')

        items = [
            create_global_variable(parent, f'{name}_{inx}', target_type.item_type)
            for inx in range(target_type.length)
        ]

        return arr.GlobalArray(parent, name, target_type, items)

    if not isinstance(target_type, t.PhysicalType):
        raise UserWarning(f'Type {name} must be representable')

    lg.debug(f'Creating a global variable {name}')
    create = el.GlobalVariable(parent, name, target_type)
    return create


def create_ptr_type(slice: el.Expression):
    if isinstance(slice.target_type, cls.InstancePointerType):
        return el.TypeWrapper(cls.InstancePointerType(slice.target_type.ref_type))

    if isinstance(slice.target_type, cls.Class):
        return el.TypeWrapper(cls.InstancePointerType(slice.target_type))

    if isinstance(slice.target_type, t.PhysicalType):
        return el.TypeWrapper(t.PointerType(slice.target_type))

    raise UserWarning(f'Unsupported pointer type {slice.target_type}')


def _funptr_validate(param_type_expr: el.Expression, return_type_expr: el.Expression):
    if not isinstance(param_type_expr, el.MetaList):
        raise UserWarning('Unsupported function pointer type (params are not a list)')

    if not isinstance(return_type_expr, el.TypeWrapper):
        raise UserWarning('Unsupported function pointer type (return type is not a type)')

    if not isinstance(return_type_expr.target_type, t.NamedPhysicalType):
        raise UserWarning(
            'Unsupported function pointer type (return type is not a named type)'
        )

    for param_type in param_type_expr.elements:
        if not isinstance(param_type, el.TypeWrapper):
            raise UserWarning('Unsupported function pointer type (param type is not a type)')

        if not isinstance(param_type.target_type, t.NamedPhysicalType):
            raise UserWarning(
                'Unsupported function pointer type (param type is not a named type)'
            )

    arg_types = [cast(t.NamedPhysicalType, e.target_type) for e in param_type_expr.elements]
    return_type = return_type_expr.target_type
    return (arg_types, return_type)


def create_funptr_type(slice: el.Expression):
    if not isinstance(slice, el.MetaList):
        raise UserWarning('Unsupported function pointer type')

    if len(slice.elements) != 2:
        raise UserWarning('Unsupported function pointer type (length is not 2)')

    param_types = slice.elements[0]
    return_type = slice.elements[1]
    (arg_types, return_type) = _funptr_validate(param_types, return_type)
    return el.TypeWrapper(ptrs.FunctionPointerType(arg_types, return_type))


def create_methptr_type(slice: el.Expression):
    if not isinstance(slice, el.MetaList):
        raise UserWarning('Unsupported method pointer type')

    if len(slice.elements) != 3:
        raise UserWarning('Unsupported method pointer type (length is not 3)')

    class_type_expr = slice.elements[0]
    param_type_expr = slice.elements[1]
    return_type_expr = slice.elements[2]

    if not isinstance(class_type_expr, el.TypeWrapper):
        raise UserWarning('Unsupported method pointer type (class type is not a type)')

    if not isinstance(class_type_expr.target_type, cls.InstancePointerType):
        raise UserWarning('Unsupported method pointer type (class type is not a class)')

    class_type = class_type_expr.target_type.ref_type
    (arg_types, return_type) = _funptr_validate(param_type_expr, return_type_expr)
    this_type = cls.InstancePointerType(class_type)
    full_arg_types = [this_type] + arg_types
    return el.TypeWrapper(meth.MethodPointerType(class_type, full_arg_types, return_type))


def create_array_type(slice: el.Expression):
    if not isinstance(slice, el.MetaList):
        raise UserWarning('Malformed array type definition')

    if len(slice.elements) != 2:
        raise UserWarning('Unsupported array type definition')

    item_type_expr = slice.elements[0]
    len_expr = slice.elements[1]

    if not isinstance(item_type_expr, el.TypeWrapper):
        raise UserWarning('Unsupported item type (item type is not a type)')

    item_type = item_type_expr.target_type

    if not isinstance(item_type, t.PhysicalType):
        raise UserWarning(f'Item type must be representable {item_type}')

    if not isinstance(len_expr, el.ConstantExpression):
        raise UserWarning('Array length must be a constant')

    value = len_expr.value

    if not isinstance(value, int):
        raise UserWarning('Array length must be an integer constant')

    if value <= 0:
        raise UserWarning('Array length must be integer')

    array_type = arr.ArrayType(item_type, value)
    return el.TypeWrapper(array_type)


def create_subscript(value: el.Expression, slice: el.Expression, target):
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
            raise UserWarning(f'Unsupported subscript slice type {slice.target_type}')


def make_bound_method_call(
    bound_ref: meth.BoundMethodRef, args: el.Expressions, target: regs.Register
):
    this = bound_ref.instance_load
    ref = bound_ref.method_load

    for arg in args:
        if not isinstance(arg, el.PhyExpression):
            raise UserWarning(f'Unsupported bound method call arg {arg}')

    # 'this' pointer is the first argument
    full_args = [this]
    full_args.extend(cast(el.PhyExpressions, args))
    call = make_method_call(ref, bound_ref.callable_type, full_args, target)
    return create_call_frame(call, full_args)


def simple_assign(target_name: n.KnownName, source: el.PhyExpression):
    lg.debug(
        f'Assigning {source}: {source.target_type}'
        ' to '
        f'{target_name.name}:{target_name.target_type}'
    )

    t_type = target_name.target_type
    e_type = source.target_type

    if isinstance(source, meth.PointerToGlobalMethod):
        e_type = source.get_method().callable_type()

    if t_type != e_type:
        raise UserWarning(f'Type mismatch {t_type} != {e_type}')

    if isinstance(target_name, el.GlobalVariable):
        load = ptrs.PointerToGlobal(target_name)
        return el.Assignor(load, source)

    if isinstance(target_name, calls.LocalVariable):
        load = ptrs.PointerToLocal(target_name)
        return el.Assignor(load, source)

    if isinstance(target_name, meth.StackPointerMember):
        load_instance = ptrs.PointerToLocal(target_name.instance_parameter)
        deref = ptrs.Deref(load_instance)
        member_load = cls.ClassMemberLoad(deref, target_name.variable)
        return el.Assignor(member_load, source)

    if isinstance(target_name, meth.GlobalPointerMember):
        load = ptrs.PointerToGlobal(target_name.instance_pointer)
        deref = ptrs.Deref(load)
        member_load = cls.ClassMemberLoad(deref, target_name.variable)
        return el.Assignor(member_load, source)

    raise UserWarning(f'Unsupported assign target {target_name.name}')


def array_assign(array: n.KnownName, index: el.PhyExpression, source: el.PhyExpression):
    e_type = source.target_type

    if not isinstance(array, arr.GlobalArray):
        raise UserWarning(f'Unsupported array assign target {array}')

    t_type = array.item_type()

    if t_type != e_type:
        raise UserWarning(f'Type mismatch {t_type} != {e_type}')

    if index.target_type != t.Int32:
        raise UserWarning(f'Unsupported index value {index}')

    load = ptrs.PointerToGlobal(array)
    item_load = arr.ArrayItemPointerLoad(load, index)
    assign = el.Assignor(item_load, source)
    return assign
