from dataclasses import dataclass
from typing import Sequence, List, Callable, cast

from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.names as n
import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.pointers as ptrs


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

    def callable_type(self):
        return ptrs.FunctionPointerType(
            [cast(t.PhysicalType, p.target_type) for p in self.formals()],
            cast(t.PhysicalType, self.return_type)
        )

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
        if not isinstance(target_type, t.PhysicalType):
            raise ValueError(f'Invalid target type {target_type}')

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


class StackVariable(n.KnownName):
    offset: int

    def __init__(
        self, namespace: n.INamespace, name: str, offset: int,
        target_type: t.PhysicalType
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
        self, namespace: n.INamespace, name: str, offset: int, target_type: t.PhysicalType
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
        self, namespace: n.INamespace, name: str, offset: int, target_type: t.PhysicalType
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


class LocalVariableAssignment(el.Assignor):
    def __init__(self, target: LocalVariable, expr: el.PhysicalExpression):
        super().__init__(target, expr)

    def json(self):
        data = super().json()
        data.update({'Class': 'LocalVariableAssignment'})
        return data

    def emit(self):
        assert isinstance(self.target, LocalVariable)
        target = self.source.target
        offset = self.target.offset
        name = self.target.name
        available = regs.get_available([target])
        temp_offset = available.pop()
        temp = available.pop()

        return flatten([
            f'// Calculating {name} to reg:{target}',
            self.source.emit(),
            f'// Assigning reg:{target} to local variable {name} at {offset}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Saving addr:{temp} to reg:{target}',
            f'mrm {target} {temp}'
        ])


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


class FunctionRef(el.PhysicalExpression):
    func: Function

    def __init__(self, func: Function, target: regs.Register):
        super().__init__(func.callable_type(), target)
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
    func_ref: el.PhysicalExpression

    def __init__(
        self, func_ref: el.PhysicalExpression, return_type: t.PhysicalType,
        target: regs.Register
    ):
        super().__init__(return_type, target)
        self.func_ref = func_ref

    def json(self):
        data = super().json()
        data['Class'] = 'FunctionCall'
        data['FunctionCall'] = self.func_ref.json()
        return data

    def emit(self):
        name = (
            self.func_ref.func.name
            if isinstance(self.func_ref, FunctionRef)
            else '<dynamic>'
        )

        return flatten([
            f'// Begin function call {name}',
            self.func_ref.emit(),
            '// Calling',
            f'cll {self.func_ref.target}',
            '// Store return value',
            f'mrr {Function.return_target} {self.target}',
        ])


class CallFrame(el.PhysicalExpression):
    actuals: list[ActualParameter]
    call: el.PhysicalExpression

    def __init__(
        self, target_type: b.TargetType,
        actuals: list[ActualParameter], call: el.PhysicalExpression,
        target: regs.Register
    ):
        super().__init__(target_type, target)
        self.actuals = actuals
        self.call = call

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
