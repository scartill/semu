
from typing import Sequence, Dict, Any


JSON = Dict[str, Any]


class TargetType:
    def json(self) -> JSON:
        return {'Builtin': 'TargetType'}


class BuiltinType(TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'BuiltinType'})
        return data


type TargetTypes = Sequence[TargetType]
Builtin = BuiltinType()
