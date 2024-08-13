from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls


class ClassVariable(n.KnownName, el.Element):
    offset: int

    def __init__(
        self, parent: 'Class', name: str, offset: int,
        target_type: b.TargetType
    ):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, target_type)
        self.offset = offset

    def json(self):
        el_data = el.Element.json(self)
        n_data = n.KnownName.json(self)
        data = {'Class': 'ClassVariable', 'Offset': self.offset}
        data.update(el_data)
        data.update(n_data)
        return data

    def emit(self):
        return f'// Class variable def {self.qualname()}:{self.target_type}'


class Class(t.PhysicalType, ns.Namespace, el.Element):
    ctor: calls.Function
    current_offset: int

    def __init__(self, name: str, parent: ns.Namespace):
        el.Element.__init__(self)
        t.PhysicalType.__init__(self, name, words=0)
        ns.Namespace.__init__(self, name, parent)
        self.current_offset = self.words * WORD_SIZE

    def json(self):
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data = {'Class': 'Class'}
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        return data

    def add_name(self, known_name: n.KnownName):
        if isinstance(known_name, calls.Function):
            static = any(lambda d: x.name == 'staticmethod' for x in known_name.decorators)

            if not static:
                raise UserWarning(f'Class {self.qualname()} cannot have non-static methods')

        return super().add_name(known_name)

    def create_variable(self, name: str, target_type: t.PhysicalType) -> el.Element:
        var = ClassVariable(self, name, self.current_offset, target_type)
        self.words += target_type.words
        self.current_offset += target_type.words * WORD_SIZE
        self.add_name(var)
        return var

    def emit(self):
        return flatten([
            f'// Class {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Class {self.qualname()} end'
        ])


class GlobalInstance(n.KnownName, el.Element, ns.Namespace):
    def __init__(self, parent: ns.Namespace, name: str, target_type: t.PhysicalType):
        el.Element.__init__(self)
        n.KnownName.__init__(self, parent, name, target_type)
        ns.Namespace.__init__(self, name, parent)

    def emit(self):
        return flatten([
            f'// Global instance {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Global instance {self.qualname()} end'
        ])

    def load_variable(self, known_name: n.KnownName, target: regs.Register) -> el.Expression:
        var = self.names.get(known_name.name)

        if not isinstance(var, el.GlobalVariableCreate):
            raise UserWarning(f'Variable {known_name.name} not found')

        return el.GlobalVariableLoad(var, target=target)
