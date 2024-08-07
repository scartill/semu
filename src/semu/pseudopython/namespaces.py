import logging as lg
from typing import Dict

import semu.pseudopython.builtins as builtins
import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs


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

    def get_name(self, name: str) -> el.KnownName | None:
        lg.debug(f'Looking up {name} in {self.namespace()}')
        return self.names.get(name)

    def create_variable(self, name: str, target_type: el.TargetType) -> el.Element:
        raise NotImplementedError()

    def load_variable(self, known_name: el.KnownName, target: regs.Register) -> el.Expression:
        raise NotImplementedError()
