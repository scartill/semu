import logging as lg
from typing import Dict, Sequence, cast
from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
import semu.pseudopython.builtins as builtins

from semu.pseudopython.elements import (
    TargetType, Register,
    KnownName,
    Element, Expression, GlobalVariableCreate, GlobalVariableLoad
)


class Namespace:
    name: str
    names: Dict[str, KnownName]

    def __init__(self, name: str, parent: 'Namespace | None'):
        self.name = name
        self.parent = parent
        self.names = dict()

        self.names.update({bi.name: bi for bi in builtins.get()})

    def namespace(self) -> str:
        prefix = self.parent.parent_prefix() if self.parent else ''
        return f'{prefix}{self.name}'

    def parent_prefix(self) -> str:
        return f'{self.namespace()}.'

    def get_name(self, name: str) -> KnownName | None:
        lg.debug(f'Looking up {name} in {self.namespace()}')
        return self.names.get(name)

    def create_variable(self, name: str, target_type: TargetType) -> Element:
        raise NotImplementedError()

    def load_variable(self, known_name: KnownName, target: Register) -> Expression:
        raise NotImplementedError()


class Function(KnownName, Namespace, Element):
    args: Sequence[str]
    body: Sequence[Element]

    def __init__(self, name: str, target_type: TargetType, parent: Namespace):
        Element.__init__(self)
        KnownName.__init__(self, name, target_type)
        Namespace.__init__(self, name, parent)
        self.args = list()
        self.body = list()

    def __str__(self) -> str:
        result = [f'Function {self.namespace()}']

        result.append('Arguments:')
        for arg in self.args:
            result.append(f'\t{arg}')

        result.extend(['Body:'])
        for expr in self.body:
            result.append(str(expr))

        return '\n'.join(result)

    def label_name(self) -> str:
        return f'_function_{self.name}'

    def emit(self) -> Sequence[str]:
        name = self.name
        body_label = self._make_label(f'{name}_body')
        return_label = self._make_label(f'{name}_return')
        entrypoint = self.label_name()

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
class Module(Namespace, Element):
    body: Sequence[Element]

    def __init__(self, name: str, parent: Namespace):
        Element.__init__(self)
        Namespace.__init__(self, name, parent)
        self.body = list()

    def create_variable(self, name: str, target_type: TargetType) -> Element:
        if name in self.names:
            raise UserWarning(f'Redefinition of the name {name}')

        lg.debug(f'Creating a global variable {name}')
        create = GlobalVariableCreate(name, target_type)
        self.names[name] = create
        return create

    def load_variable(self, known_name: KnownName, target: Register) -> Expression:
        return GlobalVariableLoad(known_name, target=target)

    def emit(self):
        result: Sequence[str] = []

        declarations_end = self._make_label('declarations_end')
        temp = self._get_temp([])

        result.extend([
            f'// Module {self.namespace()} declarations guard',
            f'push {temp}',
            f'ldr &{declarations_end} {temp}',
            f'jmp {temp}',
        ])

        globals = lambda n: isinstance(n, GlobalVariableCreate)
        functions = lambda n: isinstance(n, Function)
        others = lambda n: not isinstance(n, (GlobalVariableCreate, Function))

        for global_var in filter(globals, self.body):
            result.extend(global_var.emit())

        for function in filter(functions, self.body):
            result.extend(cast(Function, function).emit())

        result.extend([
            f'{declarations_end}:',
            f'pop {temp}',
            f'// Module {self.namespace()} body',
        ])

        for expr in filter(others, self.body):
            result.extend(expr.emit())

        result.append('hlt')
        return flatten(result)

    def __str__(self) -> str:
        result = ['Module[', f'\tname={self.name}']

        if self.names:
            result.append('\tKnownNames=[')

            for known_name in self.names.values():
                result.append(f'\t\t{str(known_name)}')

            result.append('\t]')

        if self.body:
            result.append('\tBody=[')

            for statement in self.body:
                result.append(f'\t\t{str(statement)}')

            result.append('\t]')

        result.append(']')
        return '\n'.join(result)


@dataclass
class TopLevel(Namespace, Element):
    modules: Dict[str, Module]

    def __init__(self):
        super().__init__('::', None)
        self.modules = dict()

    def namespace(self) -> str:
        return '::'

    def parent_prefix(self) -> str:
        return self.namespace()

    def emit(self):
        result: Sequence[str] = []

        for module in self.modules.values():
            result.extend(module.emit())

        return flatten(result)

    def __str__(self):
        return '\n'.join([str(module) for module in self.modules.values()])
