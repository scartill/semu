import logging as lg
from typing import Dict
from collections import namedtuple

import semu.pseudopython.builtins as builtins
import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs


NameLookup = namedtuple('NameLookup', ['namespace', 'known_name'])


class Namespace:
    name: str
    names: Dict[str, el.KnownName]

    def __init__(self, name: str, parent: 'Namespace | None'):
        self.name = name
        self.parent = parent
        self.names = dict()
        self.names.update({bi.name: bi for bi in builtins.get()})

    def json(self) -> el.JSON:
        return {
            'Namespace': self.name,
            'Names': {name: known.json() for name, known in self.names.items()}
        }

    def namespace(self) -> str:
        prefix = self.parent.parent_prefix() if self.parent else ''
        return f'{prefix}{self.name}'

    def parent_prefix(self) -> str:
        return f'{self.namespace()}.'

    def get_name(self, name: str) -> NameLookup | None:
        lg.debug(f'Looking up {name} in {self.namespace()}')

        known_name = self.names.get(name)

        if known_name:
            return NameLookup(self, known_name)

        if not self.parent:
            return None

        return self.parent.get_name(name)

    def load_const(self, known_name: el.KnownName, target: regs.Register):
        if not isinstance(known_name, el.Constant):
            raise UserWarning(f'Unsupported const reference {known_name.name}')

        return el.ConstantExpression(
            target_type=known_name.target_type, value=known_name.value,
            target=target
        )

    def create_variable(self, name: str, target_type: el.TargetType) -> el.Element:
        raise NotImplementedError()

    def load_variable(self, known_name: el.KnownName, target: regs.Register) -> el.Expression:
        raise NotImplementedError()
