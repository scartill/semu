import logging as lg

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


class StackPointerMember(n.KnownName):
    variable: cls.ClassVariable
    instance_parameter: 'InstanceFormalParameter'

    def __init__(
        self, instance_parameter: 'InstanceFormalParameter', variable: cls.ClassVariable
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


class StackPointerMemberAssignment(el.Element):
    target: StackPointerMember
    source: el.PhysicalExpression

    def __init__(self, target: StackPointerMember, source: el.PhysicalExpression):
        self.target = target
        self.source = source

    def json(self):
        data = super().json()

        data.update({
            'Class': 'StackPointerMemberAssignment',
            'Target': str(self.target),
            'Expression': self.source.json()
        })

        return data

    def emit(self):
        stack_offset = self.target.instance_parameter.offset
        member_offset = self.target.variable.inx * WORD_SIZE
        available = regs.get_available([self.source.target])
        temp_address = available.pop()
        temp_s_offset = available.pop()
        temp_m_offset = available.pop()
        name = str(self.target)

        return flatten([
            f'// Calculating value for {name}',
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

    def json(self):
        return {
            'Class': 'InstanceFormalParameter',
            'FormalParameter': calls.FormalParameter.json(self),
            'Namespace': ns.Namespace.json(self)
        }


class StackPointerMemberLoad(el.PhysicalExpression):
    member: StackPointerMember

    def __init__(self, member: StackPointerMember, target: regs.Register):
        super().__init__(member.target_type, target)
        self.member = member

    def json(self):
        data = super().json()
        data['Class'] = 'StackMemberPointerLoad'
        data['MemberPointer'] = self.member.name
        return data

    def emit(self):
        assert isinstance(self.member.instance_parameter, InstanceFormalParameter)
        stack_offset = self.member.instance_parameter.offset
        member_offset = self.member.variable.inx * WORD_SIZE
        available = regs.get_available([self.target])
        temp_address = available.pop()
        temp_s_offset = available.pop()
        temp_m_offset = available.pop()

        lg.debug(
            f'Emitting member pointer {self.member.name}'
            f' from stack offset {stack_offset}'
            f' and member offset {member_offset}'
        )

        return [
            f'// Loading member pointer {self.member.name}',
            f'ldc {stack_offset} {temp_s_offset}',
            f'lla {temp_s_offset} {temp_address}',
            f'mmr {temp_address} {temp_address}',  # dereference
            f'ldc {member_offset} {temp_m_offset}',
            f'add {temp_address} {temp_m_offset} {temp_address}',
            f'mmr {temp_address} {self.target}'    # load result
        ]


class Method(calls.Function):
    def __init__(self, name: str, parent: ns.Namespace, return_type: b.TargetType):
        super().__init__(name, parent, return_type)

    def json(self):
        data = super().json()
        data['Class'] = 'Method'
        return data


class GlobalInstanceMethod(n.KnownName):
    instance: cls.GlobalInstance
    method: Method

    def __init__(self, instance: cls.GlobalInstance, method: Method):
        super().__init__(method, method.name, t.Callable)
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


class MethodRef(el.Expression):
    instance_method: GlobalInstanceMethod

    def __init__(self, instance_method: GlobalInstanceMethod, target: regs.Register):
        super().__init__(t.Callable, target)
        self.instance_method = instance_method

    def json(self):
        data = super().json()

        data.update({
            'Class': 'MethodRef',
            'Method': f'{self.instance_method.name}@{self.instance_method.instance.name}'
        })

        return data

    def __str__(self):
        return f'{self.instance_method.name}@{self.instance_method.instance.name}'

    def emit(self):
        return [
            f'// Method reference {self.instance_method.name}',
            f'ldr &{self.instance_method.method.address_label()} {self.target}'
        ]


class MethodCall(el.PhysicalExpression):
    method_ref: MethodRef

    def __init__(self, method_ref: MethodRef, target: regs.Register):
        super().__init__(method_ref.instance_method.method.return_type, target)
        self.method_ref = method_ref

    def json(self):
        data = super().json()
        data['Class'] = 'MethodCall'
        data['Method'] = str(self.method_ref)
        return data

    def emit(self):
        name = str(self.method_ref.instance_method)

        return flatten([
            f'// Begin method call {name}',
            self.method_ref.emit(),
            '// Calling',
            f'cll {self.method_ref.target}',
            '// Store return value',
            f'mrr {calls.Function.return_target} {self.target}',
        ])
