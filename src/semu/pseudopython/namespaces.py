import logging as lg
from typing import Dict, List, Tuple, Type
from dataclasses import dataclass

import semu.pseudopython.base as b
import semu.pseudopython.elements as el
import semu.pseudopython.registers as regs


ArgDefs = List[Tuple[str, b.PPType]]


@dataclass
class NameLookup:
    namespace: 'Namespace'
    known_name: b.KnownName


class Namespace(b.INamespace):
    name: str
    names: Dict[str, b.KnownName]
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

    def add_name(self, known_name: b.KnownName):
        if known_name.name in self.names:
            raise UserWarning(f'Redefinition of the name {known_name.name}')

        lg.debug(f'Adding {known_name.name} to {self.namespace()}')
        self.names[known_name.name] = known_name

    def lookup_name_upwards(self, name: str) -> NameLookup | None:
        lg.debug(f'Looking up {name} in {self.namespace()}')
        known_name = self.names.get(name)

        if known_name:
            lg.debug(f'Found {name} in {self.namespace()} (type {known_name.pp_type})')
            return NameLookup(self, known_name)

        return self.parent.lookup_name_upwards(name)

    def get_own_name(self, name: str) -> NameLookup:
        lg.debug(f'Getting own {name} in {self.namespace()}')

        known_name = self.names.get(name)

        if not known_name:
            raise UserWarning(f'Unknown reference {name} in {self.namespace()}')

        lg.debug(f'Found own {name} in {self.namespace()} (type {known_name.pp_type})')
        return NameLookup(self, known_name)

    def load_const(self, known_name: b.KnownName, target: regs.Register):
        if not isinstance(known_name, b.Constant):
            raise UserWarning(f'Unsupported const reference {known_name.name}')

        return el.ConstantExpression(
            known_name.pp_type, known_name.value, target
        )

    def create_variable(self, name: str, pp_type: b.PPType) -> el.Element:
        raise NotImplementedError()

    def load_variable(
        self, known_name: b.KnownName, target: regs.Register
    ) -> el.PhyExpression:

        raise NotImplementedError()

    def assign_variable(self, known_name: b.KnownName) -> Type[el.Assignor]:
        raise NotImplementedError()

    def create_function(
        self, name: str, args: ArgDefs, decors: el.Expressions, pp_type: b.PPType
    ) -> 'Namespace':

        raise NotImplementedError()
