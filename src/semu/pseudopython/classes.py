import logging as lg
from typing import Callable

from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.pointers as ptrs


class ClassVariable(n.KnownName):
    inx: int

    def __init__(self, parent: 'Class', name: str, inx: int, target_type: b.TargetType):
        n.KnownName.__init__(self, parent, name, target_type)
        self.inx = inx

    def json(self):
        n_data = n.KnownName.json(self)
        data = {'Class': 'ClassVariable'}
        data.update(n_data)
        return data


class Class(t.NamedPhysicalType, ns.Namespace, el.Element):
    fun_factory: Callable | None = None
    method_factory: Callable | None = None

    def __init__(self, name: str, parent: ns.Namespace):
        el.Element.__init__(self)
        t.NamedPhysicalType.__init__(self, name)
        ns.Namespace.__init__(self, name, parent)

    def json(self):
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data = {'Class': 'Class'}
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        return data

    def create_variable(self, name: str, target_type: t.PhysicalType) -> n.KnownName:
        n_vars = len([x for x in self.names.values() if isinstance(x, ClassVariable)])
        var = ClassVariable(self, name, n_vars, target_type)
        self.add_name(var)
        return var

    def create_function(
        self, name: str, args: ns.ArgDefs,
        decors: el.Expressions, target_type: b.TargetType
    ) -> ns.Namespace:

        static = any(
            lambda d: x.name == 'staticmethod'
            for x in decors
            if isinstance(x, el.DecoratorApplication)
        )

        if static:
            lg.debug(f'Creating static method {name}')
            assert Class.fun_factory
            function = Class.fun_factory(self, name, args, decors, target_type)
        else:
            lg.debug(f'Creating instance method {name}')
            full_args: ns.ArgDefs = [('this', InstancePointerType(self))]
            full_args.extend(args)
            assert Class.method_factory
            function = Class.method_factory(self, name, full_args, decors, target_type)

        self.add_name(function)
        return function

    def emit(self):
        return flatten([
            f'// Class {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Class {self.qualname()} end'
        ])


class InstancePointerType(t.PhysicalType):
    ref_type: Class

    def __init__(self, ref_type: Class):
        self.ref_type = ref_type

    def __str__(self):
        return f'instance-pointer<{self.ref_type.name}>'

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, InstancePointerType):
            return False

        return self.ref_type == value.ref_type


class GlobalInstance(n.KnownName, el.Element, ns.Namespace):
    def __init__(self, parent: ns.Namespace, name: str, target_type: Class):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, target_type)
        ns.Namespace.__init__(self, name, parent)

    def json(self):
        data = {'Class': 'GlobalInstance'}
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        return data

    def typelabel(self):
        return 'global_instance'

    def load_variable(self, known_name: n.KnownName, target: regs.Register) -> el.Expression:
        var = self.names.get(known_name.name)

        if not isinstance(var, el.GlobalVariable):
            raise UserWarning(f'Variable {known_name.name} not found')

        return ptrs.PointerToGlobal(var, target)

    def emit(self):
        label = self.address_label()

        return flatten([
            f'// Global instance {self.qualname()}',
            f'{label}:',  # instance label
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Global instance {self.qualname()} end'
        ])


class GlobalInstanceLoad(el.PhyExpression):
    instance: GlobalInstance

    def __init__(self, instance: GlobalInstance, target: regs.Register):
        assert isinstance(instance.target_type, Class)
        pointer_type = InstancePointerType(instance.target_type)
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


class ClassMemberLoad(el.PhyExpression):
    instance_load: el.PhyExpression
    member: ClassVariable

    def __init__(
        self, instance_load: el.PhyExpression, member: ClassVariable,
        target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(member.target_type, t.PhysicalType)
        target_type = t.PointerType(member.target_type)
        super().__init__(target_type, target)
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
        temp_offset = available.pop()
        address = self.instance_load.target

        return [
            '// Loading instance pointer',
            self.instance_load.emit(),
            f'mrr {self.instance_load.target} {address}',
            f'// Loading member {self.member.name}',
            f'ldc {offset} {temp_offset}',
            f'add {address} {temp_offset} {address}',
            f'mrr {address} {self.target}'
        ]
