
from typing import Sequence, Dict, Any


JSON = Dict[str, Any]


class TargetType:
    def json(self) -> JSON:
        return {'Class': 'Type'}

    def __str__(self):
        return self.__class__.__name__


class BuiltinType(TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Class': 'Builtin'})
        return data


type TargetTypes = Sequence[TargetType]
Builtin = BuiltinType()
