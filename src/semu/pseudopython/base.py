
from typing import Sequence, Dict, Any


JSON = Dict[str, Any]


class TargetType:
    def json(self) -> JSON:
        return {'Class': 'TargetType'}

    def __str__(self) -> str:
        return 'TargetType'


class BuiltinType(TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Class': 'BuiltinType'})
        return data

    def __str__(self) -> str:
        return 'BuiltinType'


type TargetTypes = Sequence[TargetType]
Builtin = BuiltinType()
