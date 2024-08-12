from dataclasses import dataclass
from typing import Sequence


@dataclass
class TargetType:
    is_physical: bool
    words: int

    def json(self):
        return {
            'is_physical': self.is_physical,
            'words': self.words
        }

    def __str__(self):
        return self.__class__.__name__


@dataclass
class UnitType(TargetType):
    def __init__(self):
        super().__init__(False, 0)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Unit'})
        return data


@dataclass
class Int32Type(TargetType):
    def __init__(self):
        super().__init__(True, 1)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Int32'})
        return data


@dataclass
class Bool32Type(TargetType):
    def __init__(self):
        super().__init__(True, 1)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Bool32'})
        return data


@dataclass
class ModuleType(TargetType):
    def __init__(self):
        super().__init__(False, 0)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Module'})
        return data


@dataclass
class PackageType(TargetType):
    def __init__(self):
        super().__init__(False, 0)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Package'})
        return data


@dataclass
class CallableType(TargetType):
    def __init__(self):
        super().__init__(False, 0)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Callable'})  # TODO: Add more information
        return data


class ClassType(TargetType):
    def __init__(self):
        super().__init__(False, 0)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Class'})
        return data


type TargetTypes = Sequence[TargetType]

Unit = UnitType()
Int32 = Int32Type()
Bool32 = Bool32Type()
Module = ModuleType()
Package = PackageType()
Callable = CallableType()
Class = ClassType()
