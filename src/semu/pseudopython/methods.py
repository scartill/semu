import logging as lg
from typing import cast

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.classes as cls
import semu.pseudopython.calls as calls
import semu.pseudopython.pointers as ptrs


class Method(calls.Function):
    def __init__(self, name: str, parent: ns.Namespace, return_type: b.PPType):
        super().__init__(name, parent, return_type)

    def callable_type(self):
        return MethodPointerType(
            cast(cls.Class, self.parent),
            [cast(t.PhysicalType, p.pp_type) for p in self.formals()],
            cast(t.PhysicalType, self.return_type)
        )

    def json(self):
        data = super().json()
        data['Class'] = 'Method'
        return data


class PointerToGlobalMethod(ptrs.PointerToGlobal):
    def __init__(
        self, method: Method, target: regs.Register = regs.DEFAULT_REGISTER
    ):
        super().__init__(method, target)

    def get_method(self) -> Method:
        assert isinstance(self.known_name, Method)
        return self.known_name

    def json(self):
        data = super().json()
        data['Class'] = 'PointerToGlobalMethod'
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


class MethodPointerType(t.AbstractCallableType):
    class_type: cls.Class
    arg_types: t.PhysicalTypes
    return_type: t.PhysicalType

    def __init__(
        self, class_type: cls.Class,
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


class BoundMethodPointerType(b.PPType):
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


class GlobalInstancePointer(el.GlobalVariable, ns.Namespace):
    def __init__(
        self, parent: ns.Namespace, name: str, pp_type: cls.InstancePointerType
    ):
        el.GlobalVariable.__init__(self, parent, name, pp_type)
        ns.Namespace.__init__(self, name, parent)

        class_vars = [
            cv for cv in pp_type.ref_type.names.values()
            if isinstance(cv, cls.ClassVariable)
        ]

        for cv in sorted(class_vars, key=lambda x: x.inx):
            lg.debug(f'Creating pointer member for {cv.name}')
            mp = GlobalPointerMember(self, cv)
            self.add_name(mp)

        for method in pp_type.ref_type.names.values():
            if isinstance(method, Method):
                self.add_name(GlobalPointerMethod(self, method))

    def json(self):
        data = {'Class': 'GlobalInstancePointer'}
        gv_data = el.GlobalVariable.json(self)
        ns_data = ns.Namespace.json(self)
        data.update(gv_data)
        data.update(ns_data)
        return data


class GlobalPointerMember(b.KnownName):
    variable: cls.ClassVariable
    instance_pointer: GlobalInstancePointer

    def __init__(
        self, instance_pointer: GlobalInstancePointer, variable: cls.ClassVariable
    ):
        assert isinstance(variable.pp_type, t.PhysicalType)
        member_type = variable.pp_type
        super().__init__(instance_pointer, variable.name, member_type)
        self.variable = variable
        self.instance_pointer = instance_pointer

    def json(self):
        data = super().json()

        data.update({
            'Class': 'GlobalPointerMember',
            'Member': self.variable.name
        })

        return data


class GlobalPointerMethod(b.KnownName):
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


class StackPointerMember(b.KnownName):
    variable: cls.ClassVariable
    instance_parameter: InstanceFormalParameter

    def __init__(
        self, instance_parameter: InstanceFormalParameter, variable: cls.ClassVariable
    ):
        assert isinstance(variable.pp_type, t.PhysicalType)
        super().__init__(instance_parameter, variable.name, variable.pp_type)
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


class StackPointerMethod(b.KnownName):
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


class GlobalInstanceMethod(b.KnownName):
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


class BoundMethodRef(el.Expression):
    callable_type: MethodPointerType
    method_load: el.PhyExpression
    instance_load: el.PhyExpression

    def __init__(
        self, callable_type: MethodPointerType,
        method_load: el.PhyExpression, instance_load: el.PhyExpression
    ):
        super().__init__(t.AbstractCallable)
        self.callable_type = callable_type
        self.method_load = method_load
        self.instance_load = instance_load

    @staticmethod
    def from_GIM(instance_method: GlobalInstanceMethod):
        instance_load = cls.GlobalInstanceLoad(instance_method.instance)
        method_load = PointerToGlobalMethod(instance_method.method)
        ct = instance_method.method.callable_type()
        return BoundMethodRef(ct, method_load, instance_load)

    @staticmethod
    def from_GPM(global_method: GlobalPointerMethod):
        instance_load = ptrs.Deref(ptrs.PointerToGlobal(global_method.instance_pointer))
        method_load = PointerToGlobalMethod(global_method.method)
        ct = global_method.method.callable_type()
        return BoundMethodRef(ct, method_load, instance_load)

    @staticmethod
    def from_SPM(stack_method: StackPointerMethod):
        instance_load = ptrs.Deref(ptrs.PointerToLocal(stack_method.instance_parameter))
        method_load = PointerToGlobalMethod(stack_method.method)
        ct = stack_method.method.callable_type()
        return BoundMethodRef(ct, method_load, instance_load)

    def json(self):
        data = super().json()

        data.update({
            'Class': 'BoundMethodRef',
            'InstanceLoad': self.instance_load.json(),
            'MethodLoad': self.method_load.json()
        })

        return data

    def __str__(self):
        return 'bound-method'


class MethodCall(el.PhyExpression):
    method_ref: el.PhyExpression

    def __init__(
        self, method_ref: el.PhyExpression, return_type: t.PhysicalType,
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
        ])
