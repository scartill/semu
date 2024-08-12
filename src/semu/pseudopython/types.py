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


Unit = UnitType()


@dataclass
class Int32Type(TargetType):
    def __init__(self):
        super().__init__(True, 1)


Int32 = Int32Type()


@dataclass
class Bool32Type(TargetType):
    def __init__(self):
        super().__init__(True, 1)


Bool32 = Bool32Type()


@dataclass
class ModuleType(TargetType):
    def __init__(self):
        super().__init__(False, 0)


Module = ModuleType()


@dataclass
class PackageType(TargetType):
    def __init__(self):
        super().__init__(False, 0)


Package = PackageType()


@dataclass
class CallableType(TargetType):
    def __init__(self):
        super().__init__(False, 0)


Callable = CallableType()


class ClassType(TargetType):
    def __init__(self):
        super().__init__(False, 0)


Class = ClassType()
type TargetTypes = Sequence[TargetType]
