import logging as lg
from typing import Callable, cast

from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.names as n
import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.classes as cls
import semu.pseudopython.calls as calls
import semu.pseudopython.pointers as ptrs


class Method(calls.Function):
    def __init__(self, name: str, parent: ns.Namespace, return_type: b.TargetType):
        super().__init__(name, parent, return_type)

    def callable_type(self):
        return ptrs.MethodPointerType(
            cast(cls.Class, self.parent),
            [cast(t.PhysicalType, p.target_type) for p in self.formals()],
            cast(t.PhysicalType, self.return_type)
        )

    def json(self):
        data = super().json()
        data['Class'] = 'Method'
        return data


class InstanceFormalParameter(calls.FormalParameter, ns.Namespace):
    def __init__(
        self, namespace: ns.Namespace, name: str, offset: int,
        instance_type: cls.InstancePointerType
    ):
        calls.FormalParameter.__init__(self, namespace, name, offset, instance_type)
        ns.Namespace.__init__(self, name, namespace)

        for cls_var in instance_type.ref_type.names.values():
            if isinstance(cls_var, cls.ClassVariable):
                member_pointer = StackPointerMember(self, cls_var)
                self.add_name(member_pointer)

        for method in instance_type.ref_type.names.values():
            if isinstance(method, Method):
                self.add_name(StackPointerMethod(self, method))

    def json(self):
        return {
            'Class': 'InstanceFormalParameter',
            'FormalParameter': calls.FormalParameter.json(self),
            'Namespace': ns.Namespace.json(self)
        }


class GlobalInstancePointer(el.GlobalVariable, ns.Namespace):
    def __init__(
        self, parent: ns.Namespace, name: str, target_type: cls.InstancePointerType
    ):
        el.GlobalVariable.__init__(self, parent, name, target_type)
        ns.Namespace.__init__(self, name, parent)

        class_vars = [
            cv for cv in target_type.ref_type.names.values()
            if isinstance(cv, cls.ClassVariable)
        ]

        lg.debug(f'Found {len(class_vars)} class variables')

        for cv in sorted(class_vars, key=lambda x: x.inx):
            lg.debug(f'Creating pointer member for {cv.name}')
            mp = GlobalPointerMember(self, cv)
            self.add_name(mp)

        for method in target_type.ref_type.names.values():
            if isinstance(method, Method):
                self.add_name(GlobalPointerMethod(self, method))

    def json(self):
        data = {'Class': 'GlobalInstancePointer'}
        gv_data = el.GlobalVariable.json(self)
        ns_data = ns.Namespace.json(self)
        data.update(gv_data)
        data.update(ns_data)
        return data


class GlobalPointerMember(n.KnownName):
    variable: cls.ClassVariable
    instance_pointer: GlobalInstancePointer

    def __init__(
        self, instance_pointer: GlobalInstancePointer, variable: cls.ClassVariable
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


class GlobalPointerMethod(n.KnownName):
    method: Method
    instance_pointer: GlobalInstancePointer

    def __init__(
        self, instance_pointer: GlobalInstancePointer, method: Method
    ):
        super().__init__(instance_pointer, method.name, method.callable_type())
        self.method = method
        self.instance_pointer = instance_pointer

    def json(self):
        data = super().json()

        data.update({
            'Class': 'GlobalPointerMethod',
            'Member': self.method.name
        })

        return data


class StackPointerMember(n.KnownName):
    variable: cls.ClassVariable
    instance_parameter: InstanceFormalParameter

    def __init__(
        self, instance_parameter: InstanceFormalParameter, variable: cls.ClassVariable
    ):
        assert isinstance(variable.target_type, t.PhysicalType)
        super().__init__(instance_parameter, variable.name, variable.target_type)
        self.variable = variable
        self.instance_parameter = instance_parameter

    def __str__(self) -> str:
        return f'local:{self.instance_parameter.name}@{self.variable.name}'

    def json(self):
        data = super().json()
        data.update({
            'Class': 'StackMemberPointer',
            'Instance': self.instance_parameter.name,
            'Member': self.variable.name
        })


class GlobalInstancePointerLoad(el.PhyExpression):
    pointer: GlobalInstancePointer

    def __init__(self, pointer: GlobalInstancePointer, target: regs.Register):
        super().__init__(pointer.target_type, target)
        self.pointer = pointer

    def json(self):
        data = super().json()

        data.update({
            'Class': 'GlobalInstancePointerLoad',
            'Instance': self.pointer.name,
        })

        return data

    def emit(self):
        address = self.pointer.address_label()
        available = regs.get_available([self.target])
        temp_address = available.pop()

        return [
            f'// Loading member pointer {self.pointer.name}',
            f'ldr &{address} {temp_address}',
            f'mmr {temp_address} {self.target}',  # dereference
        ]


class StackPointerMemberAssignment(el.Assignor):
    def __init__(self, target: StackPointerMember, source: el.PhyExpression):
        super().__init__(target, source)

    def json(self):
        data = super().json()
        data.update({'Class': 'StackPointerMemberAssignment'})

        return data

    def emit(self):
        assert isinstance(self.target, StackPointerMember)
        stack_offset = self.target.instance_parameter.offset
        member_offset = self.target.variable.inx * WORD_SIZE
        available = regs.get_available([self.source.target])
        temp_address = available.pop()
        temp_s_offset = available.pop()
        temp_m_offset = available.pop()
        name = str(self.target)

        return flatten([
            f'// Calculating value for var:{name}',
            self.source.emit(),
            f'push {self.source.target}',
            f'// Assigning {name} of instance {stack_offset} and member {member_offset}',
            f'ldc {stack_offset} {temp_s_offset}',
            f'lla {temp_s_offset} {temp_address}',
            f'mmr {temp_address} {temp_address}',       # dereference
            f'ldc {member_offset} {temp_m_offset}',
            f'add {temp_address} {temp_m_offset} {temp_address}',
            f'pop {self.source.target}',
            f'mrm {self.source.target} {temp_address}'  # store value
        ])


class StackInstancePointerLoad(el.PhyExpression):
    instance_pointer: calls.StackVariable

    def __init__(self, instance_pointer: calls.StackVariable, target: regs.Register):
        assert isinstance(instance_pointer.target_type, cls.InstancePointerType)
        super().__init__(instance_pointer.target_type, target)
        self.instance_pointer = instance_pointer

    def json(self):
        data = super().json()

        data.update({
            'Class': 'StackInstancePointerLoad',
            'Instance': self.instance_pointer.name
        })

        return data

    def emit(self):
        stack_offset = self.instance_pointer.offset
        available = regs.get_available([self.target])
        temp_address = available.pop()
        temp_offset = available.pop()

        return [
            f'// Loading member pointer {self.instance_pointer.name}',
            f'ldc {stack_offset} {temp_offset}',
            f'lla {temp_offset} {temp_address}',
            f'mmr {temp_address} {self.target}',  # dereference
        ]


class StackPointerMethod(n.KnownName):
    method: Method
    instance_parameter: InstanceFormalParameter

    def __init__(self, instance_parameter: InstanceFormalParameter, method: Method):
        super().__init__(instance_parameter, method.name, method.callable_type())
        self.method = method
        self.instance_parameter = instance_parameter

    def __str__(self) -> str:
        return f'local:{self.instance_parameter.name}@{self.method.name}'

    def json(self):
        data = super().json()
        data.update({
            'Class': 'StackMemberMethod',
            'Instance': self.instance_parameter.name,
            'Method': self.method.name
        })

        return data


class GlobalInstanceMethod(n.KnownName):
    instance: cls.GlobalInstance
    method: Method

    def __init__(self, instance: cls.GlobalInstance, method: Method):
        super().__init__(method, method.name, method.callable_type())
        self.instance = instance
        self.method = method

    def __str__(self) -> str:
        return f'{self.method.name}@{self.instance.name}'

    def json(self):
        data = super().json()
        data.update({
            'Class': 'GlobalInstanceMethod',
            'Instance': self.instance.name,
            'Method': self.method.name
        })

        return data


type LoadFactory = Callable[[regs.Register], el.PhyExpression]


class UnboundMethodRef(el.PhyExpression):
    method: Method

    def __init__(self, method: Method, target: regs.Register):
        super().__init__(method.callable_type(), target)
        self.method = method

    def json(self):
        data = super().json()

        data.update({
            'Class': 'UnboundMethodRef',
            'Method': self.method.name
        })

        return data

    def emit(self):
        return [
            f'// Method reference {self.method.name}',
            f'ldr &{self.method.address_label()} {self.target}'
        ]

    def bind(self, instance_load: LoadFactory):
        return BoundMethodRef(self.method, instance_load, self.target)


class BoundMethodRef(el.PhyExpression):
    instance_load: LoadFactory
    method: Method

    @staticmethod
    def from_GIM(instance_method: GlobalInstanceMethod, target: regs.Register):
        load = lambda t: cls.GlobalInstanceLoad(instance_method.instance, t)
        return BoundMethodRef(instance_method.method, load, target)

    @staticmethod
    def from_GPM(global_method: GlobalPointerMethod, target: regs.Register):
        load = lambda t: GlobalInstancePointerLoad(global_method.instance_pointer, t)
        return BoundMethodRef(global_method.method, load, target)

    @staticmethod
    def from_SPM(stack_method: StackPointerMethod, target: regs.Register):
        load = lambda t: StackInstancePointerLoad(stack_method.instance_parameter, t)
        return BoundMethodRef(stack_method.method, load, target)

    def __init__(self, method: Method, instance_load: LoadFactory, target: regs.Register):
        super().__init__(method.callable_type(), target)
        self.instance_load = instance_load
        self.method = method

    def json(self):
        data = super().json()

        data.update({
            'Class': 'BoundMethodRef',
            'Method': f'method:{self.method.name}'
        })

        return data

    def __str__(self):
        return f'ref:{self.method.name}'

    def emit(self):
        return [
            f'// Method reference {self.method.name}',
            f'ldr &{self.method.address_label()} {self.target}'
        ]


class MethodCall(el.PhyExpression):
    method_ref: BoundMethodRef

    def __init__(self, method_ref: BoundMethodRef, target: regs.Register):
        super().__init__(method_ref.method.return_type, target)
        self.method_ref = method_ref

    def json(self):
        data = super().json()
        data['Class'] = 'MethodCall'
        data['Method'] = str(self.method_ref)
        return data

    def emit(self):
        name = str(self.method_ref.method.name)

        return flatten([
            f'// Begin method call {name}',
            self.method_ref.emit(),
            '// Calling',
            f'cll {self.method_ref.target}',
            '// Store return value',
            f'mrr {calls.Function.return_target} {self.target}',
        ])
