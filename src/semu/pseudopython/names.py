from typing import Any, Dict
from dataclasses import dataclass

import semu.pseudopython.base as b


JSON = Dict[str, Any]


class INamespace:
    def parent_prefix(self) -> str:
        raise NotImplementedError()


class KnownName:
    name: str
    target_type: b.TargetType
    parent: INamespace

    def __init__(self, namespace: INamespace | None, name: str, target_type: b.TargetType):
        if namespace is not None:
            self.parent = namespace
        else:
            # NB: Escape hatch for top-level names
            self.parent = INamespace()

        self.name = name
        self.target_type = target_type

    def json(self) -> JSON:
        return {'Name': self.name, 'Type': self.target_type.json()}

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
        target_type: b.TargetType, value: Any
    ):
        super().__init__(namespace, name, target_type)
        self.value = value

    def json(self) -> JSON:
        data = super().json()
        data.update({'Value': self.value})
        return data


class GlobalVariable(KnownName):
    def __init__(self, namespace: INamespace, name: str, target_type: b.TargetType):
        super().__init__(namespace, name, target_type)

    def json(self):
        data = super().json()
        data.update({'Variable': 'global'})
        return data


@dataclass
class FormalParameter(KnownName):
    inx: int

    def __init__(self, namespace: INamespace, name: str, inx: int, target_type: b.TargetType):
        KnownName.__init__(self, namespace, name, target_type)
        self.inx = inx

    def json(self):
        data = super().json()
        data['Index'] = self.inx
        return data


@dataclass
class LocalVariable(KnownName):
    inx: int

    def __init__(self, namespace: INamespace, name: str, target_type: b.TargetType, inx: int):
        KnownName.__init__(self, namespace, name, target_type)
        self.inx = inx

    def json(self):
        data = KnownName.json(self)
        data['Variable'] = 'local'
        return data
