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


class Class(t.NamedType, ns.Namespace, el.Element):
    fun_factory: Callable | None = None
    method_factory: Callable | None = None

    def __init__(self, name: str, parent: ns.Namespace):
        el.Element.__init__(self)
        t.NamedType.__init__(self, name)
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

        return el.GlobalVariableLoad(var, target=target)

    def emit(self):
        label = self.address_label()

        return flatten([
            f'// Global instance {self.qualname()}',
            f'{label}:',  # instance label
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Global instance {self.qualname()} end'
        ])


class InstancePointerType(b.TargetType):
    ref_type: Class

    def __init__(self, ref_type: Class):
        self.ref_type = ref_type

    def __str__(self):
        return f'pointer<{self.ref_type.name}>'

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, InstancePointerType):
            return False

        return self.ref_type == value.ref_type


class GlobalPointerMember(n.KnownName):
    variable: ClassVariable
    instance_pointer: 'GlobalInstancePointer'

    def __init__(
        self, instance_pointer: 'GlobalInstancePointer', variable: ClassVariable
    ):
        assert isinstance(variable.target_type, t.PhysicalType)
        super().__init__(instance_pointer, variable.name, variable.target_type)
        self.variable = variable
        self.instance_pointer = instance_pointer

    def json(self):
        data = super().json()

        data.update({
            'Class': 'GlobalPointerMember',
            'Member': self.variable.name
        })

        return data


class GlobalPointerMemberLoad(el.PhysicalExpression):
    m_pointer: GlobalPointerMember

    def __init__(self, m_pointer: GlobalPointerMember, target: regs.Register):
        super().__init__(m_pointer.target_type, target)
        self.m_pointer = m_pointer

    def json(self):
        data = super().json()

        data.update({'GlobalMemberPointerLoad': {
            'InstancePointer': self.m_pointer.instance_pointer.name,
            'MemberPointer': self.m_pointer.name
        }})

        return data

    def emit(self):
        address = self.m_pointer.instance_pointer.address_label()
        offset = self.m_pointer.variable.inx * WORD_SIZE
        available = regs.get_available([self.target])
        temp_address = available.pop()
        temp_offset = available.pop()

        return [
            f'// Loading member pointer {self.m_pointer.name}',
            f'ldr &{address} {temp_address}',
            f'mmr {temp_address} {temp_address}',  # dereference
            f'ldc {offset} {temp_offset}',
            f'add {temp_address} {temp_offset} {temp_address}',
            f'mmr {temp_address} {self.target}'    # load result
        ]


class GlobalInstancePointer(el.GlobalVariable, ns.Namespace):
    def __init__(
        self, parent: ns.Namespace, name: str, target_type: InstancePointerType
    ):
        el.GlobalVariable.__init__(self, parent, name, target_type)
        ns.Namespace.__init__(self, name, parent)

        class_vars = [
            cv for cv in target_type.ref_type.names.values()
            if isinstance(cv, ClassVariable)
        ]

        lg.debug(f'Found {len(class_vars)} class variables')

        for cv in sorted(class_vars, key=lambda x: x.inx):
            lg.debug(f'Creating pointer member for {cv.name}')
            mp = GlobalPointerMember(self, cv)
            self.add_name(mp)

    def json(self):
        data = {'Class': 'GlobalInstancePointer'}
        gv_data = el.GlobalVariable.json(self)
        ns_data = ns.Namespace.json(self)
        data.update(gv_data)
        data.update(ns_data)
        return data


class GlobalInstanceLoad(el.PhysicalExpression):
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
