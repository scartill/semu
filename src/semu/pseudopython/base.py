from dataclasses import dataclass
from typing import Sequence, Dict, Any, Set
from random import randint


type JSON = Dict[str, Any]


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


class INamespace:
    def parent_prefix(self) -> str:
        raise NotImplementedError()


class TypedObject:
    pp_type: PPType

    def __init__(self, pp_type: PPType) -> None:
        self.pp_type = pp_type

    def json(self) -> JSON:
        return {
            'Class': 'TypedObject',
            'Type': str(self.pp_type)
        }


class KnownName(TypedObject):
    name: str
    parent: INamespace

    def __init__(self, namespace: INamespace | None, name: str, pp_type: PPType):
        super().__init__(pp_type)

        if namespace is not None:
            self.parent = namespace
        else:
            # NB: Escape hatch for top-level names
            self.parent = INamespace()

        self.name = name

    def json(self) -> JSON:
        data = super().json()

        data.update({
            'Class': 'KnownName',
            'Name': self.name,
            'Type': str(self.pp_type)
        })

        return data

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


class Element:
    labels: Set[str] = set()

    def __init__(self):
        pass

    def _make_label(self, description) -> str:
        label = f'_label_{description}_{randint(1_000_000, 9_000_000)}'

        if label in Element.labels:
            return self._make_label(description)
        else:
            Element.labels.add(label)
            return label

    def emit(self) -> Sequence[str]:
        raise NotImplementedError()

    def json(self) -> JSON:
        return {'Class': 'Element'}


Elements = Sequence[Element]


@dataclass
class VoidElement(Element):
    comment: str

    def emit(self):
        return [f'// {self.comment}']

    def json(self):
        data = Element.json(self)
        data['Class'] = 'VoidElement'
        data['Void'] = self.comment
        return data


Builtin = BuiltinType()
