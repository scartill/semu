from dataclasses import dataclass
from typing import Sequence, List, Callable

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
        data['Offset'] = self.offset
        return data


class FormalParameter(StackVariable):
    def __init__(
        self, namespace: n.INamespace, name: str, offset: int, target_type: b.TargetType
    ):
        super().__init__(namespace, name, offset, target_type)


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
        data = {'Variable': 'local'}
        data_kn = n.KnownName.json(self)
        data_el = el.Element.json(self)
        data.update(data_kn)
        data.update(data_el)
        return data_kn

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
        data['Load'] = self.variable.name
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
        data = el.Element.json(self)

        data.update({
            'LocalAssign': self.target.json(),
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


class StackMemberPointer(n.KnownName):
    variable: cls.ClassVariable
    instance_parameter: 'InstanceFormalParameter'

    def __init__(
        self, instance_parameter: 'InstanceFormalParameter', variable: cls.ClassVariable
    ):
        assert isinstance(variable.target_type, t.PhysicalType)
        target_type = t.PointerType(variable.target_type)
        super().__init__(instance_parameter, variable.name, target_type)
        self.variable = variable
        self.instance_parameter = instance_parameter

    def json(self):
        return ({
            'KnownName': super().json(),
            'Class': 'StackMemberPointer',
            'MemberPointerTo': self.variable.name
        })


class InstanceFormalParameter(FormalParameter, ns.Namespace):
    def __init__(
        self, namespace: ns.Namespace, name: str, offset: int,
        instance_type: cls.InstancePointerType
    ):
        FormalParameter.__init__(self, namespace, name, offset, instance_type)
        ns.Namespace.__init__(self, name, namespace)

        for cls_var in instance_type.ref_type.names.values():
            if isinstance(cls_var, cls.ClassVariable):
                member_pointer = StackMemberPointer(self, cls_var)
                self.add_name(member_pointer)

    def json(self):
        return {
            'Class': 'InstanceFormalParameter',
            'FormalParameter': FormalParameter.json(self),
            'Namespace': ns.Namespace.json(self)
        }


class StackMemberPointerLoad(el.PhysicalExpression):
    m_pointer: StackMemberPointer

    def __init__(self, m_pointer: StackMemberPointer, target: regs.Register):
        super().__init__(m_pointer.target_type, target)
        self.m_pointer = m_pointer

    def json(self):
        data = super().json()
        data['Class'] = 'StackMemberPointerLoad'
        data['MemberPointer'] = self.m_pointer.name
        return data

    def emit(self):
        assert isinstance(self.m_pointer.instance_parameter, InstanceFormalParameter)
        stack_offset = self.m_pointer.instance_parameter.offset
        member_offset = self.m_pointer.variable.inx * WORD_SIZE
        available = regs.get_available([self.target])
        temp_address = available.pop()
        temp_s_offset = available.pop()
        temp_m_offset = available.pop()

        return [
            f'// Loading member pointer {self.m_pointer.name}',
            f'ldc {stack_offset} {temp_s_offset}',
            f'lla {temp_s_offset} {temp_address}',
            f'mmr {temp_address} {temp_address}',  # dereference
            f'ldc {member_offset} {temp_m_offset}',
            f'add {temp_address} {temp_m_offset} {temp_address}',
            f'mrr {temp_address} {self.target}'
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
        data_el = el.Element.json(self)
        data_ns = ns.Namespace.json(self)
        data_n = n.KnownName.json(self)
        data: b.JSON = {'Class': 'function'}
        data.update(data_el)
        data.update(data_ns)
        data.update(data_n)

        data.update({
            'ReturnType': self.return_type.json(),
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


class ActualParameter(el.Element):
    inx: int
    expression: el.PhysicalExpression

    def __init__(self, inx: int, expression: el.PhysicalExpression):
        super().__init__()
        self.inx = inx
        self.expression = expression

    def json(self):
        data = el.Element.json(self)

        data.update({
            'Parameter': 'actual',
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
            'Frame': 'call',
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
        data.update({'Function': self.func.name})
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
        data.update({'Return': self.return_type().json()})
        return data


@dataclass
class ReturnValue(Return):
    func: Function
    expression: el.PhysicalExpression

    def return_type(self):
        return self.expression.target_type

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

    def emit(self):
        return_label = self.func.return_label()
        temp = regs.get_temp([self.func.return_target])

        return flatten([
            f'// Returning from {self.func.name} without a value',
            f'ldc 0 {self.func.return_target}',
            f'ldr &{return_label} {temp}',
            f'jmp {temp}'
        ])


@dataclass
class FunctionCall(el.PhysicalExpression):
    func_ref: FunctionRef

    def json(self):
        data = super().json()
        data.update({'FunctionCall': self.func_ref.json()})
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
