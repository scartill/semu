
import logging as lg
from typing import Sequence, cast, Callable

from semu.pseudopython.flatten import flatten

import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.expressions as ex
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs
import semu.pseudopython.calls as calls
import semu.pseudopython.classes as cls
import semu.pseudopython.pointers as ptrs


class Module(b.KnownName, ns.Namespace, b.Element):
    fun_factory: Callable | None = None
    body: Sequence[b.Element]
    global_var_factory: Callable | None = None

    def __init__(self, name: str, parent: ns.Namespace):
        b.KnownName.__init__(self, parent, name, t.Module)
        b.Element.__init__(self)
        ns.Namespace.__init__(self, name, parent)
        self.body = list()

    def json(self):
        data: b.JSON = {'Class': 'Module'}
        data['Element'] = b.Element.json(self)
        data['Namespace'] = ns.Namespace.json(self)
        data['KnownName'] = b.KnownName.json(self)

        data.update({
            'Body': [e.json() for e in self.body if not isinstance(e, b.KnownName)]
        })

        return data

    def typelabel(self) -> str:
        return 'module'

    def create_variable(self, name: str, pp_type: b.PPType) -> b.Element:
        assert Module.global_var_factory
        creator = Module.global_var_factory(self, name, pp_type)
        self.add_name(creator)
        return creator

    def load_variable(self, known_name: b.KnownName, target: regs.Register) -> ex.Expression:
        lg.debug(f'Module variable load {known_name.name} (type: {known_name.pp_type})')
        assert isinstance(known_name, ex.GlobalVariable)
        return ptrs.PointerToGlobal(known_name, target)

    def create_function(
        self, name: str, args: ns.ArgDefs,
        decors: ex.Expressions, pp_type: b.PPType
    ) -> ns.Namespace:

        assert Module.fun_factory
        function = Module.fun_factory(self, name, args, decors, pp_type)
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

        globals = lambda n: isinstance(n, ex.GlobalVariable)
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
