from typing import Sequence, Callable
import logging as lg

# from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.pptypes as t
import semu.pseudopython.base as b
import semu.pseudopython.names as n
import semu.pseudopython.calls as calls
import semu.pseudopython.elements as el
import semu.pseudopython.pointers as ptrs


Factory = Callable[[el.Expressions, regs.Register], el.Expression]


class BuiltinInline(n.KnownName):
    factory: Factory
    return_type: b.TargetType

    def __init__(
        self, namespace: n.INamespace, name: str,
        return_type: b.TargetType,
        factory: Factory
    ):
        n.KnownName.__init__(self, namespace, name, b.Builtin)
        # Builtin functions have no address
        self.factory = factory
        self.return_type = return_type


class BuiltinInlineWrapper(el.Expression):
    inline: BuiltinInline

    def __init__(self, inline: BuiltinInline):
        super().__init__(t.BuiltinCallable)
        self.inline = inline


class Checkpoint(el.PhysicalExpression):
    arg: int

    def __init__(self, arg: int):
        super().__init__(t.Unit, regs.VOID_REGISTER)
        self.arg = arg

    def emit(self) -> Sequence[str]:
        return [
            '// Checkpoint',
            f'%check {self.arg}'
        ]

    def json(self):
        data = super().json()
        data.update({'Checkpoint': self.arg})
        return data


class Assertion(el.PhysicalExpression):
    source: el.PhysicalExpression
    value: int

    def __init__(self, source: el.PhysicalExpression, value: int):
        super().__init__(t.Unit, regs.VOID_REGISTER)
        self.source = source
        self.value = value

    def json(self):
        data = super().json()

        data.update({
            'Assert': self.value,
            'Source': self.source.json()
        })

        return data

    def emit(self) -> Sequence[str]:
        return flatten([
            self.source.emit(),
            '// Assertion',
            f'%assert {self.source.target} {self.value}',
        ])


class BoolToInt(el.PhysicalExpression):
    source: el.PhysicalExpression

    def __init__(self, source: el.PhysicalExpression, target: regs.Register):
        super().__init__(t.Int32, target)
        self.source = source

    def emit(self) -> Sequence[str]:
        # Does nothing on the assembly level
        return self.source.emit()


class Ref(el.PhysicalExpression):
    address: el.PhysicalExpression

    def __init__(
        self, target_type: t.PointerType, address: el.PhysicalExpression,
        target: regs.Register
    ):
        super().__init__(target_type, target)
        self.address = address

    def json(self):
        data = el.Expression.json(self)
        assert isinstance(self.target_type, t.PointerType)
        data.update({'RefOf': str(self.target_type)})
        return data

    def emit(self) -> el.Sequence[str]:
        return flatten([
            '// Ref target address fetch',
            self.address.emit(),
            f'mrr {self.address.target} {self.target}'
        ])


class Deref(el.PhysicalExpression):
    source: el.PhysicalExpression

    def __init__(self, source: el.PhysicalExpression, target: regs.Register):
        assert isinstance(source.target_type, t.PointerType)
        super().__init__(source.target_type.ref_type, target)
        self.source = source

    def json(self):
        data = el.Expression.json(self)
        data.update({'DerefOf': self.target_type.json()})
        return data

    def emit(self) -> el.Sequence[str]:
        assert isinstance(self.target_type, t.PhysicalType)

        return flatten([
            f'// Pointer type: {self.target_type}',
            self.source.emit(),
            '// Dereference',
            f'mmr {self.source.target} {self.target}'
        ])


class GlobalRefSet(el.PhysicalExpression):
    variable: el.GlobalVariable
    source: el.PhysicalExpression

    def __init__(self, variable: el.GlobalVariable, source: el.PhysicalExpression):
        super().__init__(t.Unit, regs.VOID_REGISTER)
        self.variable = variable
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Mode': 'global',
            'RefSet': self.variable.name,
            'Source': self.source.json()
        })

        return data

    def emit(self) -> el.Sequence[str]:
        assert isinstance(self.variable.target_type, t.PointerType)

        address_label = self.variable.address_label()
        address = regs.get_temp([self.source.target])

        return flatten([
            '// RefSet global target address load',
            f'ldr &{address_label} {address}',
            f'push {address}',
            '// RefSet source calculation',
            self.source.emit(),
            f'pop {address}',
            f'mmr {address} {address}',   # dereference
            f'mrm {self.source.target} {address}'
        ])


class LocalRefSet(el.PhysicalExpression):
    variable: calls.StackVariable
    source: el.PhysicalExpression

    def __init__(self, variable: calls.StackVariable, source: el.PhysicalExpression):
        super().__init__(t.Unit, regs.VOID_REGISTER)
        self.variable = variable
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Class': 'LocalRefSet',
            'RefSet': self.variable.name,
            'Source': self.source.json()
        })

        return data

    def emit(self):
        assert isinstance(self.variable.target_type, t.PointerType)
        offset = self.variable.offset
        available = regs.get_available([self.source.target])
        address = available.pop()
        offset_temp = available.pop()

        return flatten([
            '// RefSet local target address load',
            f'ldc {offset} {offset_temp}',
            f'lla {offset_temp} {address}',
            f'push {address}',
            '// RefSet source calculation',
            self.source.emit(),
            f'pop {address}',
            f'mmr {address} {address}',   # dereference
            f'mrm {self.source.target} {address}'
        ])


def create_checkpoint(args: el.Expressions, target: regs.Register):
    lg.debug('Checkpoint')

    if len(args) != 1:
        raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

    arg = args[0]

    if not isinstance(arg, el.ConstantExpression):
        raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

    # Inlining the checkpoint number
    value = arg.value
    return Checkpoint(value)


def create_assert(args: el.Expressions, target: regs.Register):
    if len(args) != 2:
        raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

    source = args[0]

    if not isinstance(source, el.PhysicalExpression):
        raise UserWarning(f"'assertion' expects a physical source, got {source}")

    value_expr = args[1]

    if not isinstance(value_expr, el.ConstantExpression):
        raise UserWarning(f"'assert_eq' expects a constant value, got {value_expr}")

    if source.target_type not in [t.Int32, t.Bool32]:
        raise UserWarning(
            f"'assertion' expects a int/bool source, got {source.target_type}"
        )

    if value_expr.target_type not in [t.Int32, t.Bool32]:
        raise UserWarning(
            f"'assertion' expects a int/bool value, got {value_expr.target_type}"
        )

    if source.target_type != value_expr.target_type:
        raise UserWarning(
            f"'assertion' expects source and value of the same type, "
            f"got {source.target_type} and {value_expr.target_type}"
        )

    # Inlining the value
    if value_expr.target_type == t.Int32:
        value = value_expr.value
    else:
        value = 1 if value_expr.value else 0

    return Assertion(source, value)


def create_bool2int(args: el.Expressions, target: regs.Register):
    lg.debug('BoolToInt')

    if len(args) != 1:
        raise UserWarning(f"'bool_to_int' expects 1 argument, got {len(args)}")

    source = args[0]

    if not isinstance(source, el.PhysicalExpression):
        raise UserWarning(f"'bool_to_int' expects a physical source, got {source}")

    if source.target_type != t.Bool32:
        raise UserWarning(f"'bool_to_int' expects a bool32 source, got {source.target_type}")

    return BoolToInt(source, target)


def create_deref(args: el.Expressions, target: regs.Register):
    lg.debug('Deref32')

    if len(args) != 1:
        raise UserWarning(f"'deref' expects 1 argument, got {len(args)}")

    source = args[0]

    if not isinstance(source, el.PhysicalExpression):
        raise UserWarning(f"'deref' expects a physical source, got {source}")

    if not isinstance(source.target_type, t.PointerType):
        raise UserWarning(f"'deref' expects a pointer source, got {source.target_type}")

    return Deref(source, target)


def create_refset(args: el.Expressions, target: regs.Register):
    lg.debug('RefSet')

    ref_target = args[0]
    ref_source = args[1]

    if not isinstance(ref_source, el.PhysicalExpression):
        raise UserWarning(f"'refset' expects a physical source, got {ref_source}")

    if not isinstance(ref_source.target_type, t.PhysicalType):
        raise UserWarning(f"'refset' expects a physical source, got {ref_source.target_type}")

    if not isinstance(ref_target.target_type, t.PointerType):
        raise UserWarning(f"'refset' expects a pointer target, got {ref_target.target_type}")

    if ref_source.target_type != ref_target.target_type.ref_type:
        raise UserWarning(
            f"'refset' expects a source of type {ref_target.target_type.ref_type}, "
            "got {source.target_type}"
        )

    if isinstance(ref_target, el.GlobalVariableLoad):
        return GlobalRefSet(ref_target.variable, ref_source)
    elif isinstance(ref_target, calls.StackVariableLoad):
        return LocalRefSet(ref_target.variable, ref_source)
    else:
        raise UserWarning(f"Unsupported refset target: {ref_target}")


def create_ref(args: el.Expressions, target: regs.Register):
    lg.debug('Ref')

    if len(args) != 1:
        raise UserWarning(f"'ref' expects 1 argument, got {len(args)}")

    source = args[0]
    s_type = source.target_type

    if not isinstance(s_type, t.PhysicalType):
        raise ValueError('Pointers can only point to PhysicalType')

    if isinstance(source, el.GlobalVariableLoad):
        to_known_name = source.variable
    else:
        raise UserWarning(f'Unsupported pointer assignment {source}')

    temp = regs.get_temp([source.target, target])
    load_pointer = ptrs.PointerToGlobal(to_known_name, temp)
    return Ref(t.PointerType(s_type), load_pointer, target)


def get(namespace: n.INamespace) -> Sequence[n.KnownName]:
    t.Unit.parent = namespace
    t.Int32.parent = namespace
    t.Bool32.parent = namespace
    ptrs.PointerOperator.parent = namespace

    return [
        t.Unit,
        t.Int32,
        t.Bool32,
        ptrs.PointerOperator,
        ptrs.FunctionPointerOperator,
        t.DecoratorType('staticmethod', namespace),
        BuiltinInline(namespace, 'checkpoint', t.Unit, create_checkpoint),
        BuiltinInline(namespace, 'assert_eq', t.Unit, create_assert),
        BuiltinInline(namespace, 'bool_to_int', t.Int32, create_bool2int),
        BuiltinInline(namespace, 'ref', t.AbstractPointer, create_ref),
        BuiltinInline(namespace, 'deref', t.AbstractPhysical, create_deref),
        BuiltinInline(namespace, 'refset', t.Unit, create_refset)
    ]
