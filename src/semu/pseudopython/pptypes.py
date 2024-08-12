from dataclasses import dataclass

import semu.pseudopython.base as b
import semu.pseudopython.names as n


@dataclass
class ModuleType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Module'})
        return data


@dataclass
class PackageType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Package'})
        return data


@dataclass
class CallableType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Callable'})  # TODO: Add more information
        return data


class ClassType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Class'})
        return data


@dataclass
class NamedType(b.TargetType, n.KnownName):
    def __init__(self, name: str):
        b.TargetType.__init__(self)
        n.KnownName.__init__(self, None, name, b.Builtin)


@dataclass
class UnitType(NamedType):
    def __init__(self):
        super().__init__('unit')

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Unit'})
        return data


@dataclass
class PhysicalType(NamedType):
    words: int

    def __init__(self, name: str, words: int):
        super().__init__(name)
        self.words = words


@dataclass
class Int32Type(PhysicalType):
    def __init__(self):
        super().__init__('int', 1)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Int32'})
        return data


@dataclass
class Bool32Type(PhysicalType):
    def __init__(self):
        super().__init__('bool', 1)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Bool32'})
        return data


Module = ModuleType()
Package = PackageType()
Class = ClassType()
Callable = CallableType()

Unit = UnitType()
Int32 = Int32Type()
Bool32 = Bool32Type()
