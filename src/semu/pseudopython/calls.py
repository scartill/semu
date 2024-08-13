from dataclasses import dataclass
from typing import Sequence, List, Tuple

from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.names as n
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs


@dataclass
class LoadActualParameter(el.Expression):
    inx: int
    total: int

    def emit(self) -> Sequence[str]:
        available = regs.get_available([self.target])
        temp_offset = available.pop()
        temp = available.pop()

        # NB: Note that the offset skips the return address and saved frame pointer
        offset = (self.total - self.inx + 2) * WORD_SIZE

        return [
            f'// Loading actual parameter {self.inx} of {self.total} to {self.target}',
            f'ldc -{offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Loading from address {temp} to {self.target}',
            f'mmr {temp} {self.target}'
        ]


@dataclass
class LocalVariableCreate(n.LocalVariable, el.Element):
    def __init__(
            self, namespace: n.INamespace, name: str, inx: int, target_type: b.TargetType
    ):
        el.Element.__init__(self)
        n.LocalVariable.__init__(self, namespace, name, target_type, inx)

    def json(self):
        data = {'Create': 'global'}
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


@dataclass
class LocalVariableAssignment(el.Element):
    target: n.LocalVariable
    expr: el.Expression

    def __init__(self, target: n.LocalVariable, expr: el.Expression):
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
        inx = self.target.inx
        name = self.target.name
        available = regs.get_available([target])
        temp_offset = available.pop()
        temp = available.pop()

        # NB: Offset is calculated from the frame pointer
        offset = inx * WORD_SIZE

        return flatten([
            f'// Calculating {name} to reg:{target}',
            self.expr.emit(),
            f'// Assigning reg:{target} to local variable {name} at {inx}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Saving addr:{temp} to reg:{target}',
            f'mrm {target} {temp}'
        ])


@dataclass
class LocalVariableLoad(el.Expression):
    name: n.LocalVariable

    def __init__(self, known_name: n.LocalVariable, target: regs.Register):
        super().__init__(known_name.target_type, target)
        self.name = known_name

    def json(self):
        data = el.Expression.json(self)
        data.update({'LocalLoad': self.name.name})
        return data

    def emit(self):
        available = regs.get_available([self.target])
        temp_offset = available.pop()
        temp = available.pop()

        name = self.name.name
        inx = self.name.inx
        offset = inx * WORD_SIZE

        return [
            f'// Loading local variable {name} at {inx} to reg:{self.target}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Loading from addr:{temp} to reg:{self.target}',
            f'mmr {temp} {self.target}'
        ]


ArgDefs = List[Tuple[str, b.TargetType]]


class Function(n.KnownName, ns.Namespace, el.Element):
    body: el.Elements
    return_type: b.TargetType
    return_target: regs.Register = regs.DEFAULT_REGISTER
    returns: bool = False
    local_num: int = 0

    def __init__(
            self, name: str, parent: ns.Namespace,
            args: ArgDefs, return_type: b.TargetType
    ):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, return_type)
        ns.Namespace.__init__(self, name, parent)
        self.return_type = return_type
        self.body = list()

        for inx, (arg_name, arg_type) in enumerate(args):
            self.add_name(n.FormalParameter(self, arg_name, inx, arg_type))

    def json(self):
        data_el = el.Element.json(self)
        data_ns = ns.Namespace.json(self)
        data_n = n.KnownName.json(self)
        data: b.JSON = {'Class': 'Function'}
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

    def typelabel(self) -> str:
        return 'function'

    def return_label(self) -> str:
        return f'{self.address_label()}_return'

    def formals(self):
        return list(filter(
            lambda p: isinstance(p, n.FormalParameter), self.names.values()
        ))

    def load_actual(self, formal: n.FormalParameter, target: regs.Register):
        total = len(self.formals())

        return LoadActualParameter(formal.target_type, target, formal.inx, total)

    def create_variable(self, name: str, target_type: b.TargetType) -> el.Element:
        local = LocalVariableCreate(self, name, self.local_num, target_type)
        self.local_num += 1
        self.add_name(local)
        return local

    def load_variable(self, known_name: n.KnownName, target: regs.Register) -> el.Expression:
        assert isinstance(known_name, n.LocalVariable)
        return LocalVariableLoad(known_name, target=target)

    def emit(self) -> Sequence[str]:
        name = self.name
        return_label = self.return_label()
        entrypoint = self.address_label()
        body_label = self._make_label(f'{name}_body')

        is_local = lambda e: isinstance(e, LocalVariableCreate)
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


@dataclass
class ActualParameter(el.Element):
    inx: int
    expression: el.Expression

    def __init__(self, inx: int, expression: el.Expression):
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
class CallFrame(el.Expression):
    actuals: list[ActualParameter]
    call: el.Expression

    def json(self):
        data = super().json()

        data.update({
            'Frame': 'Call',
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


@dataclass
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
    expression: el.Expression

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
class FunctionCall(el.Expression):
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
