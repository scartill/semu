
import logging as lg
from typing import Sequence, cast
from dataclasses import dataclass

from semu.pseudopython.flatten import flatten

import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs
import semu.pseudopython.calls as calls


@dataclass
class Module(n.KnownName, ns.Namespace, el.Element):
    body: Sequence[el.Element]

    def __init__(self, name: str, parent: ns.Namespace):
        n.KnownName.__init__(self, parent, name, 'module')
        el.Element.__init__(self)
        ns.Namespace.__init__(self, name, parent)
        self.body = list()

    def json(self):
        data = el.Element.json(self)

        data.update({
            'Namespace': ns.Namespace.json(self),
            'Body': [e.json() for e in self.body]
        })

        return data

    def parent_prefix(self) -> str:
        return f'{ns.Namespace.namespace(self)}::'

    def create_variable(self, name: str, target_type: n.TargetType) -> el.Element:
        if name in self.names:
            raise UserWarning(f'Redefinition of the name {name}')

        lg.debug(f'Creating a global variable {name}')
        create = el.GlobalVariableCreate(self, name, target_type)
        self.names[name] = create
        return create

    def load_variable(
            self, known_name: n.KnownName, target: regs.Register
    ) -> el.Expression:
        return el.GlobalVariableLoad(known_name, target=target)

    def emit(self):
        result: Sequence[str] = []
        declarations_end = self._make_label('declarations_end')
        temp = regs.get_temp([])

        result.extend([
            f'// Module {self.namespace()} declarations guard',
            f'ldr &{declarations_end} {temp}',
            f'jmp {temp}'
        ])

        globals = lambda n: isinstance(n, el.GlobalVariableCreate)
        functions = lambda n: isinstance(n, calls.Function)
        others = lambda n: not isinstance(n, (el.GlobalVariableCreate, calls.Function))

        for global_var in filter(globals, self.body):
            result.extend(global_var.emit())

        for function in filter(functions, self.body):
            result.extend(cast(calls.Function, function).emit())

        result.extend([
            f'{declarations_end}:',
            f'// Module {self.namespace()} body'
        ])

        for expr in filter(others, self.body):
            result.extend(expr.emit())

        result.extend([
            f'// Module {self.namespace()} end',
            'hlt'
        ])

        return flatten(result)
