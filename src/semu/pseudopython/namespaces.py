import logging as lg
from typing import Dict, List, Tuple
from dataclasses import dataclass

import semu.pseudopython.base as b
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs


ArgDefs = List[Tuple[str, b.TargetType]]


@dataclass
class NameLookup:
    namespace: 'Namespace'
    known_name: n.KnownName


class Namespace(n.INamespace):
    name: str
    names: Dict[str, n.KnownName]
    parent: 'Namespace'

    def __init__(self, name: str, parent: 'Namespace'):
        self.name = name
        self.parent = parent
        self.names = dict()

    def json(self) -> b.JSON:
        return {
            'Name': self.name,
            'Names': {name: known.json() for name, known in self.names.items()}
        }

    def namespace(self) -> str:
        prefix = self.parent.parent_prefix()
        return f'{prefix}{self.name}'

    def parent_prefix(self) -> str:
        return f'{self.namespace()}.'

    def add_name(self, known_name: n.KnownName):
        if known_name.name in self.names:
            raise UserWarning(f'Redefinition of the name {known_name.name}')

        lg.debug(f'Adding {known_name.name} to {self.namespace()}')
        self.names[known_name.name] = known_name

    def get_name(self, name: str) -> NameLookup | None:
        lg.debug(f'Looking up {name} in {self.namespace()}')

        known_name = self.names.get(name)

        if known_name:
            return NameLookup(self, known_name)

        return self.parent.get_name(name)

    def load_const(self, known_name: n.KnownName, target: regs.Register):
        if not isinstance(known_name, n.Constant):
            raise UserWarning(f'Unsupported const reference {known_name.name}')

        return el.ConstantExpression(
            target_type=known_name.target_type, value=known_name.value,
            target=target
        )

    def create_variable(self, name: str, target_type: b.TargetType) -> el.Element:
        raise NotImplementedError()

    def load_variable(
        self, known_name: n.KnownName, target: regs.Register
    ) -> el.PhysicalExpression:

        raise NotImplementedError()

    def create_function(
        self, name: str, args: ArgDefs, decors: el.Expressions, target_type: b.TargetType
    ) -> 'Namespace':

        raise NotImplementedError()
