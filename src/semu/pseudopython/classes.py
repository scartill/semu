import logging as lg
from typing import Callable, Sequence, cast

from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.expressions as ex
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls


class ClassVariable(b.KnownName):
    inx: int

    def __init__(self, parent: 'Class', name: str, inx: int, pp_type: b.PPType):
        b.KnownName.__init__(self, parent, name, pp_type)
        self.inx = inx

    def json(self):
        data = b.KnownName.json(self)
        data['Class'] = 'ClassVariable'
        return data


class MethodPointerType(t.PhysicalType):
    class_type: 'Class'
    arg_types: t.PhysicalTypes
    return_type: t.PhysicalType

    def __init__(
        self, class_type: 'Class',
        arg_types: t.PhysicalTypes, return_type: t.PhysicalType
    ):
        super().__init__()
        self.class_type = class_type
        self.arg_types = arg_types
        self.return_type = return_type

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, MethodPointerType):
            return False

        return (
            self.class_type == o.class_type
            and self.arg_types == o.arg_types
            and self.return_type == o.return_type
        )

    def __str__(self) -> str:
        return (
            f'<{self.class_type.name}::'
            f'({", ".join(str(e) for e in self.arg_types)} -> {self.return_type}>)'
        )

    def json(self):
        data = super().json()
        data.update({
            'Class': 'MethodPointerType',
            'argTypes': [e.json() for e in self.arg_types],
            'ReturnType': self.return_type.json()
        })
        return data


class BoundMethodPointerType(t.AbstractCallableType):
    unbound_type: MethodPointerType

    def __init__(self, unbound_type: MethodPointerType):
        self.unbound_type = unbound_type

    def json(self):
        data = super().json()

        data.update({
            'Class': 'BoundMethodPointerType',
            'UnboundType': str(self.unbound_type)
        })

        return data

    def __str__(self) -> str:
        return f'bound<{self.unbound_type}>'


class BoundMethodRef(ex.Expression):
    instance_load: ex.PhyExpression
    method_load: ex.PhyExpression

    def __init__(self, instance_load: ex.PhyExpression, method_load: ex.PhyExpression):
        assert isinstance(method_load.pp_type, MethodPointerType)
        super().__init__(t.AbstractCallable)
        self.instance_load = instance_load
        self.method_load = method_load

    def callable_type(self):
        assert isinstance(self.method_load.pp_type, MethodPointerType)
        return self.method_load.pp_type

    def json(self):
        data = super().json()

        data.update({
            'Class': 'BoundMethodRef',
            'InstanceLoad': self.instance_load.json(),
            'MethodLoad': self.method_load.json()
        })

        return data

    def __str__(self):
        return f'bound-method<{self.callable_type()}>'


class Method(calls.Function):
    def __init__(self, name: str, parent: ns.Namespace, return_type: b.PPType):
        calls.Function.__init__(self, name, parent, return_type)

    def get_class(self) -> 'Class':
        assert isinstance(self.parent, 'Class')
        return self.parent

    def callable_type(self):
        return MethodPointerType(
            cast('Class', self.parent),
            [cast(t.PhysicalType, p.pp_type) for p in self.formals()],
            cast(t.PhysicalType, self.return_type)
        )

    def json(self):
        data = super().json()
        data['Class'] = 'Method'
        return data


class Class(b.PPType, b.KnownName, b.Element, ns.Namespace, ex.ICompoundType):
    '''
        NB: ICompoundType here is required to support static method calls
    '''
    fun_factory: Callable | None = None
    method_factory: Callable | None = None

    def __init__(self, name: str, parent: ns.Namespace):
        b.PPType.__init__(self)
        b.KnownName.__init__(self, parent, name, b.Builtin)
        b.Element.__init__(self)
        ns.Namespace.__init__(self, name, parent)
        self.class_vars = {}

    def __str__(self):
        return f'class<{self.name}>'

    def json(self):
        data = {'Class': 'Class'}
        t_data = b.PPType.json(self)
        n_data = b.KnownName.json(self)
        el_data = b.Element.json(self)
        ns_data = ns.Namespace.json(self)
        data = {'Class': 'Class'}
        data.update(t_data)
        data.update(n_data)
        data.update(el_data)
        data.update(ns_data)
        return data

    def create_variable(self, name: str, pp_type: t.PhysicalType):
        n_vars = len(list(filter(lambda x: isinstance(x, ClassVariable), self.names.values())))
        var = ClassVariable(self, name, n_vars, pp_type)
        self.add_name(var)
        return var

    def create_function(
        self, name: str, args: ns.ArgDefs,
        decors: ex.Expressions, pp_type: b.PPType
    ) -> ns.Namespace:
        # TODO: extract to factories
        static = any(
            lambda d: x.name == 'staticmethod'
            for x in decors
            if isinstance(x, ex.DecoratorApplication)
        )

        if static:
            lg.debug(f'Creating static method {name}')
            assert Class.fun_factory
            function = Class.fun_factory(self, name, args, decors, pp_type)
        else:
            lg.debug(f'Creating instance method {name}')
            full_args: ns.ArgDefs = [('this', InstancePointerType(self))]
            full_args.extend(args)
            assert Class.method_factory
            function = Class.method_factory(self, name, full_args, decors, pp_type)

        self.add_name(function)
        return function

    def load_member(
        self, parent_load: ex.Expression, name: str, target: regs.Register
    ) -> ex.PhyExpression:
        method = self.names.get(name)

        if not isinstance(method, calls.Function):
            raise UserWarning(f'Static method {name} is not found')

        load = calls.PointerToFunction(method, target)
        return load

    def emit(self):
        return flatten([
            f'// Class {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, b.Element)],
            f'// Class {self.qualname()} end'
        ])


class ClassMember(b.Element):
    instance: 'GlobalInstance'
    classvar: ClassVariable

    def __init__(self, instance: 'GlobalInstance', classvar: ClassVariable):
        self.instance = instance
        self.classvar = classvar

    def get_instance(self):
        return self.instance

    def json(self):
        data = super().json()
        data['Class'] = 'ClassMember'
        data['ClassVariable'] = self.classvar.name
        data['Instance'] = self.instance.name
        return data

    def emit(self):
        return [
            f'// Global instance member {self.instance.qualname()}@{self.classvar.qualname()}',
            'nop'
        ]


type ClassMembers = Sequence[ClassMember]


class InstancePointerType(t.PointerType, ex.ICompoundType):
    ref_type: Class

    def __init__(self, ref_type: Class):
        self.ref_type = ref_type

    def __str__(self):
        return f'instance-pointer<{self.ref_type.name}>'

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, InstancePointerType):
            return False

        return self.ref_type == value.ref_type

    def load_member(
        self, parent_load: ex.PhyExpression, name: str, target: regs.Register
    ) -> ex.Expression:

        member = self.ref_type.names.get(name)

        if isinstance(member, ClassVariable):
            load = ClassMemberLoad(parent_load, member, target)
            return ex.Assignable(load, target, name=name)

        if isinstance(member, calls.Function):
            method_load = calls.PointerToFunction(member)
            return BoundMethodRef(parent_load, method_load)

        raise UserWarning(f'Instance member {name} not found')


class ClassMemberLoad(ex.PhyExpression):
    instance_load: ex.PhyExpression
    member: ClassVariable

    def __init__(
        self, instance_load: ex.PhyExpression, member: ClassVariable,
        target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(member.pp_type, t.PhysicalType)
        pp_type = t.PointerType(member.pp_type)
        super().__init__(pp_type, target)
        self.instance_load = instance_load
        self.member = member

    def json(self):
        data = super().json()

        data.update({
            'Class': 'ClassMemberLoad',
            'InstanceLoad': self.instance_load.json(),
            'Member': self.member.name
        })

        return data

    def emit(self):
        offset = self.member.inx * WORD_SIZE
        available = regs.get_available([self.instance_load.target, self.target])
        reg_offset = available.pop()

        return [
            f'// Loading instance pointer to {self.member.name}',
            self.instance_load.emit(),
            f'// Loading member {self.member.name} at {offset}',
            f'ldc {offset} {reg_offset}',
            f'add {self.instance_load.target} {reg_offset} {self.target}'
        ]


class GlobalInstance(b.KnownName, b.Element):
    members: ClassMembers

    def __init__(
        self, parent: ns.Namespace, name: str, pp_type: Class
    ):
        b.Element.__init__(self)
        b.KnownName.__init__(self, parent, name, pp_type)

    def json(self):
        data = {'Class': 'GlobalInstance'}
        el_data = b.Element.json(self)
        n_data = b.KnownName.json(self)
        data.update(el_data)
        data.update(n_data)
        return data

    def typelabel(self):
        return 'global_instance'

    def emit(self):
        assert self.members
        label = self.address_label()

        return flatten([
            f'// Global instance {self.qualname()}',
            f'{label}:',  # instance label
            '// Members',
            [e.emit() for e in self.members],
            f'// Global instance {self.qualname()} end'
        ])


class GlobalInstanceLoad(ex.PhyExpression):
    instance: GlobalInstance

    def __init__(
        self, instance: GlobalInstance, target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(instance.pp_type, Class)
        pointer_type = InstancePointerType(instance.pp_type)
        super().__init__(pointer_type, target)
        self.instance = instance

    def json(self):
        data = super().json()
        data.update({'GlobalInstanceLoad': self.instance.name})
        return data

    def emit(self):
        return [
            f'// Creating pointer to global instance {self.instance.qualname()}',
            f'ldr &{self.instance.address_label()} {self.target}',
        ]


class MethodCall(ex.PhyExpression):
    method_ref: ex.PhyExpression

    def __init__(
        self, method_ref: ex.PhyExpression, return_type: t.PhysicalType,
        target: regs.Register
    ):
        super().__init__(return_type, target)
        self.method_ref = method_ref

    def json(self):
        data = super().json()
        data['Class'] = 'MethodCall'
        data['Method'] = self.method_ref.json()
        return data

    def emit(self):
        return flatten([
            '// Begin method call',
            self.method_ref.emit(),
            '// Calling',
            f'cll {self.method_ref.target}',
            '// Store return value',
            f'mrr {calls.Function.return_target} {self.target}',
            '// End method call'
        ])
