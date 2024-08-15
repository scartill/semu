from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.helpers as h
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.calls as calls


class ClassVariable(n.KnownName):
    def __init__(self, parent: 'Class', name: str, target_type: b.TargetType):
        n.KnownName.__init__(self, parent, name, target_type)

    def json(self):
        n_data = n.KnownName.json(self)
        data = {'Class': 'ClassVariable'}
        data.update(n_data)
        return data


class Class(t.PhysicalType, ns.Namespace, el.Element):
    ctor: calls.Function

    def __init__(self, name: str, parent: ns.Namespace):
        el.Element.__init__(self)
        t.PhysicalType.__init__(self, name)
        ns.Namespace.__init__(self, name, parent)

    def json(self):
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data = {'Class': 'Class'}
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        return data

    def create_variable(self, name: str, target_type: t.PhysicalType) -> n.KnownName:
        var = ClassVariable(self, name, target_type)
        self.add_name(var)
        return var

    def create_function(
        self, name: str, args: ns.ArgDefs,
        decors: el.Expressions, target_type: b.TargetType
    ) -> ns.Namespace:

        static = any(
            lambda d: x.name == 'staticmethod'
            for x in decors
            if isinstance(x, el.DecoratorApplication)
        )

        if static:
            function = h.create_function(self, name, args, decors, target_type)
        else:
            raise UserWarning(f'Class {self.qualname()} cannot have non-static methods')

        self.add_name(function)
        return function

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

    def json(self):
        data = {'Class': 'GlobalInstance'}
        el_data = el.Element.json(self)
        ns_data = ns.Namespace.json(self)
        n_data = n.KnownName.json(self)
        data.update(el_data)
        data.update(ns_data)
        data.update(n_data)
        return data

    def emit(self):
        return flatten([
            f'// Global instance {self.qualname()}',
            [e.emit() for e in self.names.values() if isinstance(e, el.Element)],
            f'// Global instance {self.qualname()} end'
        ])

    def load_variable(self, known_name: n.KnownName, target: regs.Register) -> el.Expression:
        var = self.names.get(known_name.name)

        if not isinstance(var, el.GlobalVariable):
            raise UserWarning(f'Variable {known_name.name} not found')

        return el.GlobalVariableLoad(var, target=target)
