from typing import Any

import semu.pseudopython.base as b


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

    def json(self) -> b.JSON:
        return {'Name': self.name, 'Type': str(self.target_type)}

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

    def json(self):
        data = super().json()
        data.update({'Value': self.value})
        return data
