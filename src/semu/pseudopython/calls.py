from dataclasses import dataclass
from typing import Sequence, List, Callable
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


class StackVariable(n.KnownName):
    offset: int

    def __init__(
        self, namespace: n.INamespace, name: str, offset: int,
        target_type: b.TargetType
    ):
        n.KnownName.__init__(self, namespace, name, target_type)
        self.offset = offset

    def json(self):
        data = super().json()
        data['Class'] = 'StackVariable'
        data['Offset'] = self.offset
        return data


class FormalParameter(StackVariable):
    def __init__(
        self, namespace: n.INamespace, name: str, offset: int, target_type: b.TargetType
    ):
        super().__init__(namespace, name, offset, target_type)

    def json(self):
        data = super().json()
        data['Class'] = 'FormalParameter'
        return data


class SimpleFormalParameter(FormalParameter):
    def __init__(
        self, namespace: n.INamespace, name: str, offset: int,
        target_type: t.PhysicalType
    ):
        super().__init__(namespace, name, offset, target_type)

    def json(self):
        data = super().json()
        data['Class'] = 'SimpleFormalParameter'
        return data


class LocalVariable(StackVariable, el.Element):
    def __init__(
        self, namespace: n.INamespace, name: str, offset: int, target_type: b.TargetType
    ):
        el.Element.__init__(self)
        StackVariable.__init__(self, namespace, name, offset, target_type)

    def json(self):
        data = super().json()
        data['Class'] = 'LocalVariable'
        data['KnownName'] = n.KnownName.json(self)
        data['Element'] = el.Element.json(self)
        return data

    def emit(self):
        temp = regs.get_temp([])

        return [
            f'// Creating local variable {self.name} of type {self.target_type}',
            f'ldc 0 {temp}',
            f'push {temp}',
            f'// End variable {self.name}'
        ]


class StackVariableLoad(el.PhysicalExpression):
    variable: StackVariable

    def __init__(self, variable: StackVariable, target: regs.Register):
        super().__init__(variable.target_type, target)
        self.variable = variable

    def json(self):
        data = super().json()
        data['Class'] = 'StackVariableLoad'
        data['Variable'] = self.variable.name
        return data

    def emit(self):
        available = regs.get_available([self.target])
        temp_offset = available.pop()
        temp = available.pop()
        offset = self.variable.offset

        return [
            f'// Loading actual parameter at offset:{offset}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Loading from address {temp} to {self.target}',
            f'mmr {temp} {self.target}'
        ]


class LocalVariableAssignment(el.Element):
    target: LocalVariable
    expr: el.PhysicalExpression

    def __init__(self, target: LocalVariable, expr: el.PhysicalExpression):
        self.target = target
        self.expr = expr

    def json(self):
        data = super().json()

        data.update({
            'Class': 'LocalVariableAssignment',
            'Target': str(self.target),
            'Expression': self.expr.json()
        })

        return data

    def emit(self):
        target = self.expr.target
        offset = self.target.offset
        name = self.target.name
        available = regs.get_available([target])
        temp_offset = available.pop()
        temp = available.pop()

        return flatten([
            f'// Calculating {name} to reg:{target}',
            self.expr.emit(),
            f'// Assigning reg:{target} to local variable {name} at {offset}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Saving addr:{temp} to reg:{target}',
            f'mrm {target} {temp}'
        ])


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


class InstanceFormalParameter(FormalParameter, ns.Namespace):
    def __init__(
        self, namespace: ns.Namespace, name: str, offset: int,
        instance_type: cls.InstancePointerType
    ):
        FormalParameter.__init__(self, namespace, name, offset, instance_type)
        ns.Namespace.__init__(self, name, namespace)

        for cls_var in instance_type.ref_type.names.values():
            if isinstance(cls_var, cls.ClassVariable):
                member_pointer = StackPointerMember(self, cls_var)
                self.add_name(member_pointer)

    def json(self):
        return {
            'Class': 'InstanceFormalParameter',
            'FormalParameter': FormalParameter.json(self),
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


class Function(n.KnownName, ns.Namespace, el.Element):
    factory: Callable | None = None

    decorators: List[el.DecoratorApplication]
    body: el.Elements
    return_type: b.TargetType
    return_target: regs.Register = regs.DEFAULT_REGISTER
    returns: bool = False
    local_num: int = 0

    def __init__(self, name: str, parent: ns.Namespace, return_type: b.TargetType):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, return_type)
        ns.Namespace.__init__(self, name, parent)
        self.decorators = list()
        self.return_type = return_type
        self.body = list()

    def json(self):
        data: b.JSON = {'Class': 'Function'}
        data['Element'] = el.Element.json(self)
        data['Namespace'] = ns.Namespace.json(self)
        data['Knownname'] = n.KnownName.json(self)

        data.update({
            'ReturnType': str(self.return_type),
            'Body': [e.json() for e in self.body],
            'Returns': self.returns,
            'ReturnTarget': self.return_target
        })

        return data

    def add_decorator(self, decorator: el.DecoratorApplication):
        self.decorators.append(decorator)

    def typelabel(self) -> str:
        return 'function'

    def return_label(self) -> str:
        return f'{self.address_label()}_return'

    def formals(self):
        return list(filter(
            lambda p: isinstance(p, FormalParameter), self.names.values()
        ))

    def create_variable(self, name: str, target_type: b.TargetType) -> el.Element:
        offset = self.local_num * WORD_SIZE
        self.local_num += 1
        local = LocalVariable(self, name, offset, target_type)
        self.add_name(local)
        return local

    def load_variable(self, known_name: n.KnownName, target: regs.Register):
        assert isinstance(known_name, StackVariable)
        return StackVariableLoad(known_name, target)

    def create_function(
        self, name: str, args: ns.ArgDefs,
        decors: el.Expressions, target_type: b.TargetType
    ) -> ns.Namespace:

        assert Function.factory
        function = Function.factory(self, name, args, decors, target_type)
        self.add_name(function)
        return function

    def emit(self) -> Sequence[str]:
        name = self.name
        return_label = self.return_label()
        entrypoint = self.address_label()
        body_label = self._make_label(f'{name}_body')

        is_local = lambda e: isinstance(e, LocalVariable)
        is_nested = lambda e: isinstance(e, Function)
        is_body = lambda e: not is_local(e) and not is_nested(e)
        locals = list(filter(is_local, self.body))
        nested = list(filter(is_nested, self.body))
        body = filter(is_body, self.body)
        dump_target = regs.get_temp([self.return_target])

        return flatten([
            f'// Function {name} declaration',
            [n.emit() for n in nested],
            f'// Function {name} entrypoint',
            f'{entrypoint}:',
            f'// Function {name} prologue',
            [d.emit() for d in locals],
            f'// Function {name} body',
            f'{body_label}:',
            [e.emit() for e in body],
            f'// Function {name} epilogue',
            f'{return_label}:',
            [f'pop {dump_target}' for _ in locals],
            f'// Function {name} return',
            'ret'
        ])


class Method(Function):
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


class ActualParameter(el.Element):
    inx: int
    expression: el.PhysicalExpression

    def __init__(self, inx: int, expression: el.PhysicalExpression):
        super().__init__()
        self.inx = inx
        self.expression = expression

    def json(self):
        data = super().json()

        data.update({
            'Class': 'ActualParameter',
            'Index': self.inx,
            'Expression': self.expression.json()
        })

        return data

    def emit(self):
        return flatten([
            f'// Actual parameter {self.inx} calculating',
            self.expression.emit(),
            f'// Actual parameter {self.inx} storing',
            f'push {self.expression.target}'
        ])


@dataclass
class CallFrame(el.PhysicalExpression):
    actuals: list[ActualParameter]
    call: el.PhysicalExpression

    def json(self):
        data = super().json()

        data.update({
            'Class': 'CallFrame',
            'Actuals': [a.json() for a in self.actuals],
            'Call': self.call.json()
        })

        return data

    def emit(self):
        dump = regs.get_temp([self.target])

        return flatten([
            '// Begin call frame',
            [actual.emit() for actual in self.actuals],
            self.call.emit(),
            '// Unwinding',
            [
                [
                    f'// Unwinding actual parameter {actual.inx}',
                    f'pop {dump}'
                ]
                for actual in self.actuals
            ],
            '// End call frame'
        ])


class FunctionRef(el.Expression):
    func: Function

    def __init__(self, func: Function, target: regs.Register):
        super().__init__(t.Callable, target)
        self.func = func

    def json(self):
        data = super().json()

        data.update({
            'Class': 'FunctionRef',
            'Function': self.func.name
        })

        return data

    def emit(self):
        return [
            f'// Function reference {self.func.namespace()}',
            f'ldr &{self.func.address_label()} {self.target}'
        ]


@dataclass
class Return(el.Element):
    def return_type(self) -> b.TargetType:
        raise NotImplementedError()

    def json(self):
        data = el.Element.json(self)
        data['Class'] = 'Return'
        data['ReturnType'] = str(self.return_type())
        return data


@dataclass
class ReturnValue(Return):
    func: Function
    expression: el.PhysicalExpression

    def return_type(self):
        return self.expression.target_type

    def json(self):
        data = super().json()
        data.update({
            'Class': 'ReturnValue',
            'Function': self.func.name,
            'Expression': self.expression.json()
        })

        return data

    def emit(self):
        return_label = self.func.return_label()

        temp = regs.get_temp([
            self.expression.target,
            self.func.return_target
        ])

        return flatten([
            '// Calculating return value',
            self.expression.emit(),
            f'// Returning from {self.func.name}',
            f'mrr {self.expression.target} {self.func.return_target}',
            f'ldr &{return_label} {temp}',
            f'jmp {temp}'
        ])


@dataclass
class ReturnUnit(el.Element):
    func: Function

    def return_type(self):
        return t.Unit

    def json(self):
        data = super().json()
        data.update({
            'Class': 'ReturnUnit',
            'Function': self.func.name,
        })

        return data

    def emit(self):
        return_label = self.func.return_label()
        temp = regs.get_temp([self.func.return_target])

        return flatten([
            f'// Returning from {self.func.name} without a value',
            f'ldc 0 {self.func.return_target}',
            f'ldr &{return_label} {temp}',
            f'jmp {temp}'
        ])


class FunctionCall(el.PhysicalExpression):
    func_ref: FunctionRef

    def __init__(self, func_ref: FunctionRef, target: regs.Register):
        super().__init__(func_ref.func.return_type, target)
        self.func_ref = func_ref

    def json(self):
        data = super().json()
        data['Class'] = 'FunctionCall'
        data['FunctionCall'] = self.func_ref.json()
        return data

    def emit(self):
        return flatten([
            f'// Begin function call {self.func_ref.func.name}',
            self.func_ref.emit(),
            '// Calling',
            f'cll {self.func_ref.target}',
            '// Store return value',
            f'mrr {Function.return_target} {self.target}',
        ])


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
            f'mrr {Function.return_target} {self.target}',
        ])
