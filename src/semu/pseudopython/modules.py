
import logging as lg
from typing import Sequence, cast
from dataclasses import dataclass

from semu.pseudopython.flatten import flatten

import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.registers as regs
import semu.pseudopython.calls as calls
import semu.pseudopython.builtins as builtins
import semu.sasm.asm as asm


@dataclass
class Module(el.KnownName, ns.Namespace, el.Element):
    body: Sequence[el.Element]

    def __init__(self, name: str, parent: ns.Namespace):
        el.KnownName.__init__(self, name, 'module')
        el.Element.__init__(self)
        ns.Namespace.__init__(self, name, parent)
        self.body = list()

    def json(self) -> el.JSON:
        data = el.Element.json(self)

        data.update({
            'Namespace': ns.Namespace.json(self),
            'Body': [e.json() for e in self.body]
        })

        return data

    def create_variable(self, name: str, target_type: el.TargetType) -> el.Element:
        if name in self.names:
            raise UserWarning(f'Redefinition of the name {name}')

        lg.debug(f'Creating a global variable {name}')
        create = el.GlobalVariableCreate(name, target_type)
        self.names[name] = create
        return create

    def load_variable(self, known_name: el.KnownName, target: regs.Register) -> el.Expression:
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


@dataclass
class TopLevel(ns.Namespace):
    def __init__(self):
        super().__init__('::', None)
        self.names.update({bi.name: bi for bi in builtins.get()})

    def json(self) -> el.JSON:
        data = ns.Namespace.json(self)
        data.update({'Top': True})
        return data

    def namespace(self) -> str:
        return '::'

    def parent_prefix(self) -> str:
        return self.namespace()

    def emit(self):
        def item(module: Module):
            item = asm.CompilationItem()
            item.modulename = module.name
            item.contents = '\n'.join(module.emit())
            return item

        return [item(cast(Module, n)) for n in self.names.values() if isinstance(n, Module)]
