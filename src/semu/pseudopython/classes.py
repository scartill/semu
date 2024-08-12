from dataclasses import dataclass

from semu.pseudopython.flatten import flatten
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls


@dataclass
class ClassVariable(n.KnownName, el.Element):
    inx: int

    def __init__(
        self, parent: 'Class', name: str, inx: int,
        target_type: b.TargetType
    ):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, target_type)

    def json(self):
        el_data = el.Element.json(self)
        n_data = n.KnownName.json(self)
        data = {'Class': 'ClassVariable'}
        data.update(el_data)
        data.update(n_data)
        return data

    def emit(self):
        return f'// Class variable def {self.qualname()}'


@dataclass
class Class(t.PhysicalType, ns.Namespace, el.Element):
    ctor: calls.Function
    num_vars: int

    def __init__(self, name: str, parent: ns.Namespace):
        el.Element.__init__(self)
        t.NamedType.__init__(self, name)
        ns.Namespace.__init__(self, name, parent)
        self.num_vars = 0

    def json(self):
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data = {'Class': 'Class'}
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        return data

    def emit(self):
        return flatten([
            f'// Class {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Class {self.qualname()} end'
        ])

    def create_variable(self, name: str, target_type: t.PhysicalType) -> el.Element:
        var = ClassVariable(self, name, self.num_vars, target_type)
        self.words += target_type.words
        self.num_vars += 1
        self.names[name] = var
        return var


@dataclass
class InstanceType(b.TargetType):
    classdef: Class

    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Class': self.classdef.name})
        return data


@dataclass
class Instance(n.KnownName, el.Element):
    def __init__(self, parent: ns.Namespace, name: str, target_type: InstanceType):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, target_type)
