import ast
import logging as lg
from typing import List, cast, TypeVar
from pathlib import Path

import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.pointers as ptrs
import semu.pseudopython.expressions as ex
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls
import semu.pseudopython.namespaces as ns
import semu.pseudopython.modules as mods
import semu.pseudopython.packages as pack
import semu.pseudopython.arrays as arr


class CompileSettings:
    verbose: bool
    pp_path: str
    produce_ast: bool

    def __init__(self):
        self.verbose = False
        self.pp_path = ''
        self.produce_ast = False

    def update(
        self,
        verbose: bool | None = None,
        pp_path: str | None = None,
        produce_ast: bool | None = None
    ):
        if verbose is not None:
            self.verbose = verbose

        if pp_path is not None:
            self.pp_path = pp_path

        if produce_ast is not None:
            self.produce_ast = produce_ast

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


def get_constant_value(pp_type: b.PPType, source: ast.AST):
    if pp_type == t.Int32:
        return int32const(source)

    if pp_type == t.Bool32:
        return bool32const(source)

    raise UserWarning(f'Unsupported constant type {pp_type}')


TFunction = TypeVar('TFunction', calls.Function, cls.Method)


def validate_function(func: calls.Function):
    if func.return_type != t.Unit and not func.returns:
        raise UserWarning(f'Function {func.name} does not return')


def validate_call(arg_types: t.PhysicalTypes, args: ex.Expressions):
    if len(arg_types) != len(args):
        raise UserWarning(
            f'Argument count mismatch: need {len(arg_types)}, got {len(args)}'
        )

    for arg_type, arg in zip(arg_types, args):
        if arg_type != arg.pp_type:
            raise UserWarning(
                f'Argument type mismatch: need {arg_type}, got {arg.pp_type}'
            )


def find_module(namespace: ns.Namespace, names: List[str]):
    name = names.pop(0)

    try:
        lookup = namespace.lookup_name_upwards(name)
    except pack.NotFoundOnTopLevel:
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


def funptr_validate(param_type_expr: ex.Expression, return_type_expr: ex.Expression):
    if not isinstance(param_type_expr, ex.MetaList):
        raise UserWarning('Unsupported function pointer type (params are not a list)')

    if not isinstance(return_type_expr, ex.TypeWrapper):
        raise UserWarning('Unsupported function pointer type (return type is not a type)')

    if not isinstance(return_type_expr.pp_type, t.PhysicalType):
        raise UserWarning(
            'Unsupported function pointer type (return type is not a named type)'
        )

    for param_type in param_type_expr.elements:
        if not isinstance(param_type, ex.TypeWrapper):
            raise UserWarning('Unsupported function pointer type (param type is not a type)')

        if not isinstance(param_type.pp_type, t.PhysicalType):
            raise UserWarning(
                'Unsupported function pointer type (param type is not a named type)'
            )

    arg_types = [cast(t.PhysicalType, e.pp_type) for e in param_type_expr.elements]
    return_type = return_type_expr.pp_type
    return (arg_types, return_type)


def simple_assign(assignable: ex.Assignable, source: ex.PhyExpression):
    lg.debug(
        f'Assigning {source}: {source.pp_type}'
        ' to '
        f'{assignable.name}:{assignable.pp_type}'
    )

    t_type = assignable.valuetype()
    e_type = source.pp_type

    if t_type != e_type:
        raise UserWarning(f'Type mismatch: target {t_type}, source {e_type}')

    return ex.Assignor(assignable, source)


def array_assign(array: b.KnownName, index: ex.PhyExpression, source: ex.PhyExpression):
    e_type = source.pp_type

    if not isinstance(array, arr.GlobalArray):
        raise UserWarning(f'Unsupported array assign target {array}')

    t_type = array.item_type()

    if t_type != e_type:
        raise UserWarning(f'Type mismatch {t_type} != {e_type}')

    if index.pp_type != t.Int32:
        raise UserWarning(f'Unsupported index value {index}')

    load = ptrs.PointerToGlobal(array)
    item_load = arr.ArrayItemLoad(load, index)
    assign = ex.Assignor(ex.Assignable(item_load), source)
    return assign
