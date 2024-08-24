
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


type PPTypes = Sequence[PPType]
Builtin = BuiltinType()


class INamespace:
    def parent_prefix(self) -> str:
        raise NotImplementedError()


class KnownName:
    name: str
    pp_type: PPType
    parent: INamespace

    def __init__(self, namespace: INamespace | None, name: str, pp_type: PPType):
        if namespace is not None:
            self.parent = namespace
        else:
            # NB: Escape hatch for top-level names
            self.parent = INamespace()

        self.name = name
        self.pp_type = pp_type

    def json(self) -> JSON:
        return {
            'Class': 'KnownName',
            'Name': self.name,
            'Type': str(self.pp_type)
        }

    def qualname(self) -> str:
        return f'{self.parent.parent_prefix()}{self.name}'

    def typelabel(self) -> str:
        raise NotImplementedError()

    def address_label(self) -> str:
        return f'_{self.typelabel()}_{self.qualname()}'


class Constant(KnownName):
    value: Any

    def __init__(
        self, namespace: INamespace, name: str,
        pp_type: PPType, value: Any
    ):
        super().__init__(namespace, name, pp_type)
        self.value = value

    def json(self):
        data = super().json()
        data['Class'] = 'Constant'
        data['Value'] = self.value
        return data
