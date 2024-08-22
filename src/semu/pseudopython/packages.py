import logging as lg
from pathlib import Path

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.builtins as bi
import semu.pseudopython.modules as mods


class Package(ns.Namespace, n.KnownName, el.Element):
    path: Path

    def __init__(self, name: str, parent: ns.Namespace, path: Path):
        el.Element.__init__(self)
        ns.Namespace.__init__(self, name, parent)
        n.KnownName.__init__(self, parent, name, t.Package)
        self.path = path

    def json(self):
        data_el = el.Element.json(self)
        data_ns = ns.Namespace.json(self)
        data_n = n.KnownName.json(self)
        data: b.JSON = {'Class': 'Package'}
        data.update(data_el)
        data.update(data_ns)
        data.update(data_n)
        return data

    def emit(self):
        return flatten([
            f'// Package {self.name}',
            [
                item.emit()
                for item in self.names.values()
                if isinstance(item, (mods.Module, Package))
            ],
            f'// End of package {self.name}'
        ])


class TopLevel(ns.Namespace, el.Element):
    main: mods.Module | None = None

    def __init__(self):
        super().__init__('<top>', self)
        self.names.update({b.name: b for b in bi.get(self)})

    def json(self):
        data: b.JSON = {'Class': 'TopLevel'}
        data['Element'] = el.Element.json(self)
        data['Namespace'] = ns.Namespace.json(self)
        return data

    def namespace(self) -> str:
        return '<top>'

    def parent_prefix(self) -> str:
        return ''

    def lookup_name_upwards(self, name: str) -> ns.NameLookup | None:
        lg.debug(f'Looking up {name} on the top level')

        if known_name := self.names.get(name):
            lg.debug(f'Found {name} on the top level (type {known_name.target_type})')
            return ns.NameLookup(self, known_name)
        else:
            return None

    def emit(self):
        temp = regs.get_temp([])

        if self.main is None:
            raise UserWarning('No main module defined')

        entrypoint = self.main.address_label()

        return flatten([
            '// Jump to the entrypoint',
            f'ldr &{entrypoint} {temp}',
            f'jmp {temp}',
            [
                item.emit()
                for item in self.names.values()
                if isinstance(item, (mods.Module, Package))
            ]
        ])
