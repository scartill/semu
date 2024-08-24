
from typing import Sequence, Dict, Any


JSON = Dict[str, Any]


class PPType:
    def json(self) -> JSON:
        return {'Class': 'PPType'}

    def __str__(self) -> str:
        return 'pp-type'


class BuiltinType(PPType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Class': 'BuiltinType'})
        return data

    def __str__(self) -> str:
        return 'BuiltinType'


type TargetTypes = Sequence[PPType]
Builtin = BuiltinType()
