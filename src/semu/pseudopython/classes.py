from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
import semu.pseudopython.elements as el
import semu.pseudopython.names as n
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls


@dataclass
class Class(n.KnownName, ns.Namespace, el.Element):
    ctor: calls.Function

    def __init__(self, name: str, parent: ns.Namespace):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, 'class')
        ns.Namespace.__init__(self, name, parent)

    def json(self):
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data = {}
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        data.update({})  # 'Ctor': self.ctor.json()
        return data

    def emit(self):
        return flatten([
            f'// class {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// class {self.qualname()} end'
        ])
