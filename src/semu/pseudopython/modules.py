
from typing import Sequence, cast
from dataclasses import dataclass

from semu.pseudopython.flatten import flatten

import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.helpers as h
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls


@dataclass
class Module(n.KnownName, ns.Namespace, el.Element):
    body: Sequence[el.Element]

    def __init__(self, name: str, parent: ns.Namespace):
        n.KnownName.__init__(self, parent, name, t.Module)
        el.Element.__init__(self)
        ns.Namespace.__init__(self, name, parent)
        self.body = list()

    def json(self):
        data_el = el.Element.json(self)
        data_ns = ns.Namespace.json(self)
        data_n = n.KnownName.json(self)
        data: b.JSON = {'Class': 'Module'}
        data.update(data_el)
        data.update(data_ns)
        data.update(data_n)

        data.update({
            'Body': [e.json() for e in self.body if not isinstance(e, n.KnownName)]
        })

        return data

    def typelabel(self) -> str:
        return 'module'

    def create_variable(self, name: str, target_type: b.TargetType) -> el.Element:
        creator = h.create_global_variable(self, name, target_type)
        self.add_name(creator)
        return creator

    def load_variable(
        self, known_name: n.KnownName, target: regs.Register
    ) -> el.Expression:

        return el.GlobalVariableLoad(known_name, target=target)

    def create_function(
        self, name: str, args: ns.ArgDefs,
        decors: el.Expressions, target_type: b.TargetType
    ) -> ns.Namespace:

        function = h.create_function(self, name, args, decors, target_type)
        self.add_name(function)
        return function

    def emit(self):
        result: Sequence[str] = []
        declarations_end = self._make_label('declarations_end')
        temp = regs.get_temp([])

        address = self.address_label()

        result.extend([
            f'// --------- Module {self.qualname()} -----------',
            f'{address}:',
            f'// Module {self.qualname()} declarations guard',
            f'ldr &{declarations_end} {temp}',
            f'jmp {temp}'
        ])

        globals = lambda n: isinstance(n, el.GlobalVariableCreate)
        functions = lambda n: isinstance(n, calls.Function)
        classes = lambda n: isinstance(n, cls.Class)
        others = lambda n: not globals(n) and not functions(n) and not classes(n)

        for global_var in filter(globals, self.body):
            result.extend(global_var.emit())

        for function in filter(functions, self.body):
            result.extend(cast(calls.Function, function).emit())

        for classdef in filter(classes, self.body):
            result.extend(cast(cls.Class, classdef).emit())

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
