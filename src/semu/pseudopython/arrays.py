from typing import Sequence

from semu.pseudopython.flatten import flatten
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.namespaces as ns
import semu.pseudopython.classes as cls


class ArrayOperatorType(el.BuiltinMetaoperator):
    def __init__(self):
        super().__init__('array')


ArrayOperator = ArrayOperatorType()


class ArrayType(b.TargetType):
    item_type: t.PhysicalType
    length: int

    def __init__(self, item_type: t.PhysicalType, length: int):
        super().__init__()
        self.item_type = item_type
        self.length = length

    def __str__(self):
        return f'array<{self.item_type}, {self.length}>'

    def json(self):
        data = super().json()
        data['Class'] = 'ArrayType'
        data['ItemType'] = str(self.item_type)
        data['Length'] = self.length


class GlobalArray(el.Element, n.KnownName, ns.Namespace):
    items: Sequence['Globals']

    def __init__(
        self, namespace: ns.Namespace, name: str, target_type: ArrayType,
        items: Sequence['Globals']
    ):
        el.Element.__init__(self)
        n.KnownName.__init__(self, namespace, name, target_type)
        ns.Namespace.__init__(self, name, namespace)
        self.items = items

    def typelabel(self) -> str:
        return 'global_array'

    def json(self):
        data: b.JSON = {'Class': 'GlobalArray'}
        data['KnownName'] = n.KnownName.json(self)
        data['Element'] = el.Element.json(self)
        data['Namespace'] = ns.Namespace.json(self)
        return data

    def emit(self):
        label = self.address_label()
        tt = self.target_type
        assert isinstance(tt, ArrayType)

        return flatten([
            f'// Begin global array {self.name} of type {tt}',
            f'{label}:',                            # label
            [e.emit() for e in self.items],         # items
            f'// End global array {self.name}'
        ])


type Globals = el.GlobalVariable | cls.GlobalInstance | GlobalArray
