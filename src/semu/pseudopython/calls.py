from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs


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
    func: ns.Function

    def __init__(self, func: ns.Function, target: regs.Register):
        super().__init__('callable', target)
        self.func = func

    def emit(self):
        return [
            f'// Function reference {self.func.name}',
            f'ldr &{self.func.label_name()} {self.target}'
        ]


@dataclass
class FunctionCall(el.Expression):
    func_ref: FunctionRef

    def emit(self) -> ns.Sequence[str]:
        return flatten([
            f'// Begin function call {self.func_ref.func.name}',
            self.func_ref.emit(),
            '// Calling',
            f'cll {self.func_ref.target}',
            '// Store return value',
            f'mrr {ns.Function.RETURN_TARGET} {self.target}',
        ])
