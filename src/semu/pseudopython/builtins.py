from typing import Sequence, Callable
import logging as lg

# from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.pptypes as t
import semu.pseudopython.base as b
import semu.pseudopython.expressions as ex
import semu.pseudopython.pointers as ptrs
import semu.pseudopython.arrays as arr


Factory = Callable[[ex.Expressions, regs.Register], ex.Expression]


class BuiltinInline(b.KnownName):
    factory: Factory
    return_type: b.PPType

    def __init__(
        self, namespace: b.INamespace, name: str,
        return_type: b.PPType,
        factory: Factory
    ):
        b.KnownName.__init__(self, namespace, name, b.Builtin)
        # Builtin functions have no address
        self.factory = factory
        self.return_type = return_type


class BuiltinInlineWrapper(ex.Expression):
    inline: BuiltinInline

    def __init__(self, inline: BuiltinInline):
        super().__init__(t.BuiltinCallable)
        self.inline = inline


class Checkpoint(ex.PhyExpression):
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


class Assertion(ex.PhyExpression):
    source: ex.PhyExpression
    value: int

    def __init__(self, source: ex.PhyExpression, value: int):
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


class BoolToInt(ex.PhyExpression):
    source: ex.PhyExpression

    def __init__(self, source: ex.PhyExpression, target: regs.Register):
        super().__init__(t.Int32, target)
        self.source = source

    def emit(self) -> Sequence[str]:
        # Does nothing on the assembly level
        return self.source.emit()


def create_checkpoint(args: ex.Expressions, target: regs.Register):
    lg.debug('Checkpoint')

    if len(args) != 1:
        raise UserWarning(f"'checkpoint' expects 1 argument, got {len(args)}")

    arg = args[0]

    if not isinstance(arg, ex.ConstantExpression):
        raise UserWarning(f"'checkpoint' expects a constant argument, got {arg}")

    # Inlining the checkpoint number
    value = arg.value
    return Checkpoint(value)


def create_assert(args: ex.Expressions, target: regs.Register):
    if len(args) != 2:
        raise UserWarning(f"'assertion' expects 2 arguments, got {len(args)}")

    source = args[0]

    if not isinstance(source, ex.PhyExpression):
        raise UserWarning(f"'assertion' expects a physical source, got {source}")

    if isinstance(source, ex.Assignable):
        source = ptrs.Deref(source)

    value_expr = args[1]

    if not isinstance(value_expr, ex.ConstantExpression):
        raise UserWarning(f"'assert_eq' expects a constant value, got {value_expr}")

    if source.pp_type not in [t.Int32, t.Bool32]:
        raise UserWarning(
            f"'assertion' expects a int/bool source, got {source.pp_type}"
        )

    if value_expr.pp_type not in [t.Int32, t.Bool32]:
        raise UserWarning(
            f"'assertion' expects a int/bool value, got {value_expr.pp_type}"
        )

    if source.pp_type != value_expr.pp_type:
        raise UserWarning(
            f"'assertion' expects source and value of the same type, "
            f"got {source.pp_type} and {value_expr.pp_type}"
        )

    # Inlining the value
    if value_expr.pp_type == t.Int32:
        value = value_expr.value
    else:
        value = 1 if value_expr.value else 0

    return Assertion(source, value)


def create_bool2int(args: ex.Expressions, target: regs.Register):
    lg.debug('BoolToInt')

    if len(args) != 1:
        raise UserWarning(f"'bool_to_int' expects 1 argument, got {len(args)}")

    source = args[0]

    if not isinstance(source, ex.PhyExpression):
        raise UserWarning(f"'bool_to_int' expects a physical source, got {source}")

    if source.pp_type != t.Bool32:
        raise UserWarning(f"'bool_to_int' expects a bool32 source, got {source.pp_type}")

    return BoolToInt(source, target)


def create_deref(args: ex.Expressions, target: regs.Register):
    lg.debug('Deref32')

    if len(args) != 1:
        raise UserWarning(f"'deref' expects 1 argument, got {len(args)}")

    source = args[0]

    if not isinstance(source, ex.PhyExpression):
        raise UserWarning(f"'deref' expects a physical source, got {source}")

    if not isinstance(source.pp_type, t.PointerType):
        raise UserWarning(f"'deref' expects a pointer source, got {source.pp_type}")

    return ptrs.Deref(source, target)


def create_refset(args: ex.Expressions, target: regs.Register):
    if len(args) != 2:
        raise UserWarning(f"'refset' expects 2 arguments, got {len(args)}")

    assignable = args[0]

    if not isinstance(assignable, ex.Assignable):
        raise UserWarning(f"'refset' expects an assignable pointer, got {assignable}")

    pointer_to_target = assignable.pointer
    ref_source = args[1]

    if not isinstance(ref_source, ex.PhyExpression):
        raise UserWarning(f"'refset' expects a physical source, got {ref_source}")

    assert isinstance(pointer_to_target.pp_type, t.PointerType)
    ptt_type = pointer_to_target.pp_type.ref_type

    if not isinstance(ptt_type, t.PointerType):
        raise UserWarning(
            f"'refset' expects a pointer target, got {pointer_to_target.pp_type}"
        )

    if ref_source.pp_type != ptt_type.ref_type:
        raise UserWarning(
            f"'refset' expects a source of type {ptt_type.ref_type}, "
            f"got {ref_source.pp_type}"
        )

    available = regs.get_available([pointer_to_target.target, ref_source.target, target])
    assignable_target = available.pop()
    assignor_target = available.pop()
    assignable_of_pointer = ex.Assignable(pointer_to_target, assignable_target)
    return ex.Assignor(assignable_of_pointer, ref_source, assignor_target)


def create_ref(args: ex.Expressions, target: regs.Register):
    lg.debug('Ref')

    if len(args) != 1:
        raise UserWarning(f"'ref' expects 1 argument, got {len(args)}")

    assignable = args[0]

    if not isinstance(assignable, ex.Assignable):
        raise UserWarning(f"'ref' expects an assignable, got {assignable}")

    source = assignable.pointer
    return ex.Retarget(source, target)


def get(namespace: b.INamespace) -> Sequence[b.KnownName]:
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
        ptrs.MethodPointerOperator,
        arr.ArrayOperator,
        t.DecoratorType(namespace, 'staticmethod'),
        BuiltinInline(namespace, 'checkpoint', t.Unit, create_checkpoint),
        BuiltinInline(namespace, 'assert_eq', t.Unit, create_assert),
        BuiltinInline(namespace, 'bool_to_int', t.Int32, create_bool2int),
        BuiltinInline(namespace, 'ref', t.AbstractPointer, create_ref),
        BuiltinInline(namespace, 'deref', t.AbstractPhysical, create_deref),
        BuiltinInline(namespace, 'refset', t.Unit, create_refset)
    ]
