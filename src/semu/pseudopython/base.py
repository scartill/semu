
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
class BuiltinType(TargetType):
    def __init__(self):
        super().__init__(False, 0)

    def json(self):
        data = super().json()
        data.update({'Class': 'Builtin'})
        return data


type TargetTypes = Sequence[TargetType]
Builtin = BuiltinType()
