from dataclasses import dataclass
from typing import cast

import semu.pseudopython.namespaces as ns
import semu.pseudopython.builtins as bi
import semu.pseudopython.modules as mod

import semu.sasm.asm as asm


@dataclass
class TopLevel(ns.Namespace):
    def __init__(self):
        super().__init__('<top>', self)
        self.names.update({bi.name: bi for bi in bi.get()})

    def json(self):
        data = ns.Namespace.json(self)
        data.update({'Top': True})
        return data

    def namespace(self) -> str:
        return ''

    def parent_prefix(self) -> str:
        return '%'

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
class Package(ns.Namespace):
    def json(self):
        return {'Package': True}
