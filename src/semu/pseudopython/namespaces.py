import logging as lg
from typing import Dict
from collections import namedtuple

import semu.pseudopython.types as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs


NameLookup = namedtuple('NameLookup', ['namespace', 'known_name'])


class Namespace(n.INamespace):
    name: str
    names: Dict[str, n.KnownName]
    parent: 'Namespace'

    def __init__(self, name: str, parent: 'Namespace'):
        self.name = name
        self.parent = parent
        self.names = dict()

    def json(self) -> n.JSON:
        return {
            'Namespace': self.name,
            'Names': {name: known.json() for name, known in self.names.items()}
        }

    def namespace(self) -> str:
        prefix = self.parent.parent_prefix()
        return f'{prefix}{self.name}'

    def parent_prefix(self) -> str:
        return f'{self.namespace()}.'

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

    def create_variable(self, name: str, target_type: t.TargetType) -> el.Element:
        raise NotImplementedError()

    def load_variable(self, known_name: n.KnownName, target: regs.Register) -> el.Expression:
        raise NotImplementedError()
