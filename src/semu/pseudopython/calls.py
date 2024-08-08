from dataclasses import dataclass
from typing import Sequence, List, Tuple

from semu.pseudopython.flatten import flatten
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs


@dataclass
class FormalParameter(el.KnownName):
    inx: int

    def __init__(self, name: str, inx: int, target_type: el.TargetType):
        el.KnownName.__init__(self, name, target_type)
        self.inx = inx

    def json(self) -> el.JSON:
        data = super().json()
        data['Index'] = self.inx
        return data


@dataclass
class LoadActualParameter(el.Expression):
    inx: int
    total: int

    def emit(self) -> Sequence[str]:
        available = regs.get_available([self.target])
        temp_a = available.pop()
        temp_b = available.pop()

        return [
            f'// Loading actual parameter {self.inx} of {self.total}',
            f'ldc {self.total} {temp_a}',
            f'ldc {self.inx} {temp_b}',
            f'sub {temp_a} {temp_b} {temp_a}',
            f'ldc 2 {temp_b}',
            f'add {temp_a} {temp_b} {temp_a}',
            f'ldc -4 {temp_b}',
            f'mul {temp_a} {temp_b} {temp_a}',
            f'lla {temp_a} {self.target}'
        ]


ArgDefs = List[Tuple[str, el.TargetType]]


class Function(el.KnownName, ns.Namespace, el.Element):
    body: el.Elements
    return_type: el.TargetType
    return_target: regs.Register = regs.DEFAULT_REGISTER
    returns: bool = False

    def __init__(
            self, name: str, parent: ns.Namespace,
            args: ArgDefs, return_type: el.TargetType
    ):
        el.Element.__init__(self)
        el.KnownName.__init__(self, name, return_type)
        ns.Namespace.__init__(self, name, parent)
        self.return_type = return_type
        self.body = list()

        for inx, (arg_name, arg_type) in enumerate(args):
            self.names[arg_name] = FormalParameter(arg_name, inx, arg_type)

    def json(self) -> el.JSON:
        data = el.Element.json(self)

        data.update({
            'KnownName': el.KnownName.json(self),
            'Namespace': ns.Namespace.json(self),
            'Function': {
                'ReturnType': self.return_type,
                'Body': [e.json() for e in self.body],
                'Returns': self.returns,
                'ReturnTarget': self.return_target
            }
        })

        return data

    def address_label(self) -> str:
        return f'_function_{self.name}'

    def return_label(self) -> str:
        return f'_function_{self.name}_return'

    def load_actual(self, formal: FormalParameter, target: regs.Register):
        total = len(list(filter(
            lambda n: isinstance(n, FormalParameter), self.names.values()
        )))

        return LoadActualParameter(formal.target_type, target, formal.inx, total)

    def emit(self) -> Sequence[str]:
        name = self.name
        return_label = self.return_label()
        entrypoint = self.address_label()
        body_label = self._make_label(f'{name}_body')

        return flatten([
            f'// function {name} entrypoint',
            f'{entrypoint}:',
            f'// function {name} prologue',
            f'// function {name} body',
            f'{body_label}:',
            [e.emit() for e in self.body],
            f'{return_label}:',
            'ret',
        ])


@dataclass
class ActualParameter(el.Element):
    inx: int
    expression: el.Expression

    def __init__(self, inx: int, expression: el.Expression):
        super().__init__()
        self.inx = inx
        self.expression = expression

    def json(self) -> el.JSON:
        data = el.Element.json(self)

        data.update({
            'Parameter': 'actual',
            'Index': self.inx,
            'Expression': self.expression.json()
        })

        return data

    def emit(self):
        return flatten([
            f'//Actual parameter {self.inx} calculating',
            self.expression.emit(),
            f'// Actual parameter {self.inx} storing',
            f'push {self.expression.target}'
        ])


@dataclass
class UnwindActualParameter(el.Element):
    actual: ActualParameter
    target: regs.Register

    def json(self) -> el.JSON:
        data = super().json()

        data.update({
            'Parameter': 'unwind',
            'Actual': self.actual.inx,
            'Target': self.target
        })

        return data

    def emit(self):
        return [
            f'//Unwinding actual parameter {self.actual.inx}',
            f'pop {self.target}'
        ]


@dataclass
class CallFrame(el.Expression):
    actuals: list[ActualParameter]
    call: el.Expression
    unwinds: list[UnwindActualParameter]

    def json(self) -> el.JSON:
        data = super().json()

        data.update({
            'Frame': 'Call',
            'Actuals': [a.json() for a in self.actuals],
            'Call': self.call.json(),
            'Unwinds': [uw.json() for uw in self.unwinds]
        })

        return data

    def emit(self):
        return flatten([
            '// Begin call frame',
            [actual.emit() for actual in self.actuals],
            self.call.emit(),
            [unwind.emit() for unwind in self.unwinds],
            '// End call frame'
        ])


@dataclass
class FunctionRef(el.Expression):
    func: Function

    def __init__(self, func: Function, target: regs.Register):
        super().__init__('callable', target)
        self.func = func

    def json(self) -> el.JSON:
        data = super().json()

        data.update({
            'Function': self.func.json()
        })

        return data

    def emit(self):
        return [
            f'// Function reference {self.func.namespace()}',
            f'ldr &{self.func.address_label()} {self.target}'
        ]


@dataclass
class Return(el.Element):
    def return_type(self) -> el.TargetType:
        raise NotImplementedError()

    def json(self) -> el.JSON:
        data = el.Element.json(self)
        data.update({'Return': self.return_type()})
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
        return 'unit'

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

    def json(self) -> el.JSON:
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
