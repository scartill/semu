from dataclasses import dataclass
from typing import Sequence

from semu.pseudopython.flatten import flatten
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs


class Function(el.KnownName, ns.Namespace, el.Element):
    args: Sequence[str]
    body: Sequence[el.Element]
    return_target: regs.Register = regs.DEFAULT_REGISTER

    def __init__(self, name: str, parent: ns.Namespace, return_type: el.TargetType):
        el.Element.__init__(self)
        el.KnownName.__init__(self, name, return_type)
        ns.Namespace.__init__(self, name, parent)
        self.args = list()
        self.body = list()

    def __str__(self) -> str:
        result = [f'Function {self.name} [']

        result.append('Arguments:')
        for arg in self.args:
            result.append(f'{arg}')

        result.extend(['Body:'])
        for expr in self.body:
            result.append(str(expr))

        result.append(']')

        return '\n'.join(result)

    def address_label(self) -> str:
        return f'_function_{self.name}'

    def return_label(self) -> str:
        return f'_function_{self.name}_return'

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

    def emit(self):
        return flatten([
            '// Begin call frame',
            [actual.emit() for actual in self.actuals],
            self.call.emit(),
            [unwind.emit() for unwind in self.unwinds],
            '// End call frame'
        ])

    def __str__(self) -> str:
        return f'''CallFrame[
            Actuals={self.actuals}
            Call={self.call}
            Unwind={','.join(str(uw) for uw in self.unwinds)}
        ]'''


@dataclass
class FunctionRef(el.Expression):
    func: Function

    def __init__(self, func: Function, target: regs.Register):
        super().__init__('callable', target)
        self.func = func

    def emit(self):
        return [
            f'// Function reference {self.func.name}',
            f'ldr &{self.func.address_label()} {self.target}'
        ]


@dataclass
class Return(el.Element):
    def return_type(self) -> el.TargetType:
        raise NotImplementedError()


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
            self.emit(),
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

    def emit(self):
        return flatten([
            f'// Begin function call {self.func_ref.func.name}',
            self.func_ref.emit(),
            '// Calling',
            f'cll {self.func_ref.target}',
            '// Store return value',
            f'mrr {Function.return_target} {self.target}',
        ])