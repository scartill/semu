from dataclasses import dataclass
from typing import cast
import logging as lg
from pathlib import Path

import semu.pseudopython.names as n
import semu.pseudopython.namespaces as ns
import semu.pseudopython.builtins as bi
import semu.pseudopython.modules as mod

import semu.sasm.asm as asm


@dataclass
class TopLevel(ns.Namespace):
    def __init__(self):
        super().__init__('<top>', self)
        self.names.update({b.name: b for b in bi.get(self)})

    def json(self):
        data = ns.Namespace.json(self)
        data.update({'Top': True})
        return data

    def namespace(self) -> str:
        return ''

    def parent_prefix(self) -> str:
        return ''

    def get_name(self, name: str) -> ns.NameLookup | None:
        lg.debug(f'Looking up {name} on the top level')

        if known_name := self.names.get(name):
            return ns.NameLookup(self, known_name)
        else:
            return None

    def emit(self):
        def item(module: mod.Module):
            item = asm.CompilationItem()
            item.modulename = module.name
            item.contents = '\n'.join(module.emit())
            return item

        return [
            item(cast(mod.Module, n))
            for n in self.names.values()
            if isinstance(n, mod.Module)
        ]


@dataclass
class Package(ns.Namespace, n.KnownName):
    path: Path

    def __init__(self, name: str, parent: ns.Namespace, path: Path):
        ns.Namespace.__init__(self, name, parent)
        n.KnownName.__init__(self, parent, name, 'package')
        self.path = path

    def json(self):
        return {'Package': True, 'Path:': str(self.path)}
