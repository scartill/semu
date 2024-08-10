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
        temp_offset = available.pop()
        temp = available.pop()

        # NB: Note that the offset skips the return address and saved frame pointer
        offset = (self.total - self.inx + 2) * 4

        return [
            f'// Loading actual parameter {self.inx} of {self.total} to {self.target}',
            f'ldc -{offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Loading from address {temp} to {self.target}',
            f'mmr {temp} {self.target}'
        ]


@dataclass
class LocalVariable(el.KnownName):
    inx: int

    def __init__(self, name: str, target_type: el.TargetType, inx: int):
        el.KnownName.__init__(self, name, target_type)
        self.inx = inx

    def json(self) -> el.JSON:
        data = el.KnownName.json(self)
        data['Variable'] = 'local'
        return data


@dataclass
class LocalVariableCreate(LocalVariable, el.Element):
    def __init__(self, name: str, inx: int, target_type: el.TargetType):
        el.Element.__init__(self)
        LocalVariable.__init__(self, name, target_type, inx)

    def json(self) -> el.JSON:
        data = {'Create': 'global'}
        data_kn = el.KnownName.json(self)
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
    target: LocalVariable
    expr: el.Expression

    def __init__(self, target: LocalVariable, expr: el.Expression):
        self.target = target
        self.expr = expr

    def json(self) -> el.JSON:
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
        offset = inx * 4

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
    name: LocalVariable

    def __init__(self, known_name: LocalVariable, target: regs.Register):
        super().__init__(known_name.target_type, target)
        self.name = known_name

    def json(self) -> el.JSON:
        data = el.Expression.json(self)
        data.update({'LocalLoad': self.name.name})
        return data

    def emit(self):
        available = regs.get_available([self.target])
        temp_offset = available.pop()
        temp = available.pop()

        name = self.name.name
        inx = self.name.inx
        offset = inx * 4

        return [
            f'// Loading local variable {name} at {inx} to reg:{self.target}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {temp}',
            f'// Loading from addr:{temp} to reg:{self.target}',
            f'mmr {temp} {self.target}'
        ]


ArgDefs = List[Tuple[str, el.TargetType]]


class Function(el.KnownName, ns.Namespace, el.Element):
    body: el.Elements
    return_type: el.TargetType
    return_target: regs.Register = regs.DEFAULT_REGISTER
    returns: bool = False
    local_num: int = 0

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

    def formals(self):
        return list(filter(
            lambda n: isinstance(n, FormalParameter), self.names.values()
        ))

    def load_actual(self, formal: FormalParameter, target: regs.Register):
        total = len(self.formals())

        return LoadActualParameter(formal.target_type, target, formal.inx, total)

    def emit(self) -> Sequence[str]:
        name = self.name
        return_label = self.return_label()
        entrypoint = self.address_label()
        body_label = self._make_label(f'{name}_body')

        is_definition = lambda e: isinstance(e, LocalVariableCreate)
        not_definitions = lambda e: not is_definition(e)
        definitions = list(filter(is_definition, self.body))
        body = filter(not_definitions, self.body)
        dump_target = regs.get_temp([self.return_target])

        return flatten([
            f'// function {name} entrypoint',
            f'{entrypoint}:',
            f'// function {name} prologue',
            [d.emit() for d in definitions],
            f'// function {name} body',
            f'{body_label}:',
            [e.emit() for e in body],
            f'// function {name} epilogue',
            f'{return_label}:',
            [f'pop {dump_target}' for _ in definitions],
            'ret',
        ])

    def create_variable(self, name: str, target_type: el.TargetType) -> el.Element:
        local = LocalVariableCreate(name, self.local_num, target_type)
        self.local_num += 1
        self.names[name] = local
        return local

    def load_variable(self, known_name: el.KnownName, target: regs.Register) -> el.Expression:
        assert isinstance(known_name, LocalVariable)
        return LocalVariableLoad(known_name, target=target)


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
class CallFrame(el.Expression):
    actuals: list[ActualParameter]
    call: el.Expression

    def json(self) -> el.JSON:
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
