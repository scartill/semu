from typing import Any, Dict, Literal, Sequence
from dataclasses import dataclass


JSON = Dict[str, Any]
TargetType = Literal['unit', 'int32', 'bool32', 'callable', 'module']
TargetTypes = Sequence[TargetType]


class INamespace:
    def parent_prefix(self) -> str:
        raise NotImplementedError()


class KnownName:
    name: str
    target_type: TargetType
    parent: INamespace

    def __init__(self, namespace: INamespace, name: str, target_type: TargetType):
        self.parent = namespace
        self.name = name
        self.target_type = target_type

    def json(self) -> JSON:
        return {'Name': self.name, 'Type': self.target_type}

    def address_label(self) -> str:
        raise NotImplementedError()


class Constant(KnownName):
    value: Any

    def __init__(self, namespace: INamespace, name: str, target_type: TargetType, value: Any):
        super().__init__(namespace, name, target_type)
        self.value = value

    def json(self) -> JSON:
        data = super().json()
        data.update({'Value': self.value})
        return data


class GlobalVariable(KnownName):
    def __init__(self, namespace: INamespace, name: str, target_type: TargetType):
        super().__init__(namespace, name, target_type)

    def address_label(self) -> str:
        return f'_global_{self.name}'

    def json(self):
        data = super().json()
        data.update({'Variable': 'global'})
        return data


@dataclass
class FormalParameter(KnownName):
    inx: int

    def __init__(self, namespace: INamespace, name: str, inx: int, target_type: TargetType):
        KnownName.__init__(self, namespace, name, target_type)
        self.inx = inx

    def json(self):
        data = super().json()
        data['Index'] = self.inx
        return data


@dataclass
class LocalVariable(KnownName):
    inx: int

    def __init__(self, namespace: INamespace, name: str, target_type: TargetType, inx: int):
        KnownName.__init__(self, namespace, name, target_type)
        self.inx = inx

    def json(self):
        data = KnownName.json(self)
        data['Variable'] = 'local'
        return data
