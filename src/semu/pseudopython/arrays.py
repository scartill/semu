from typing import List

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
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


class ArrayType(t.PhysicalType):
    item_type: t.PhysicalType
    length: int

    def __init__(self, item_type: t.PhysicalType, length: int):
        super().__init__()
        self.item_type = item_type
        self.length = length

    def __eq__(self, value: object) -> bool:
        return (
            isinstance(value, ArrayType)
            and value.item_type == self.item_type
            and value.length == self.length
        )

    def __str__(self):
        return f'array<{self.item_type}, {self.length}>'

    def json(self):
        data = super().json()
        data['Class'] = 'ArrayType'
        data['ItemType'] = str(self.item_type)
        data['Length'] = self.length


class GlobalArray(el.Element, n.KnownName):
    items: List['Globals']

    def __init__(
        self, namespace: ns.Namespace, name: str, target_type: ArrayType,
        items: List['Globals']
    ):
        el.Element.__init__(self)
        n.KnownName.__init__(self, namespace, name, target_type)
        self.items = items

    def typelabel(self) -> str:
        return 'global_array'

    def json(self):
        data: b.JSON = {'Class': 'GlobalArray'}
        data['KnownName'] = n.KnownName.json(self)
        data['Element'] = el.Element.json(self)
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


class GlobalArrayLoad(el.PhysicalExpression):
    array: GlobalArray

    def __init__(self, array: GlobalArray, target: regs.Register):
        assert isinstance(array.target_type, ArrayType)
        pointer_type = t.PointerType(array.target_type)
        super().__init__(pointer_type, target)
        self.array = array

    def json(self):
        data = super().json()
        data.update({'GlobalArrayLoad': self.array.name})
        return data

    def emit(self):
        return [
            f'// Creating pointer to global array {self.array.qualname()}',
            f'ldr &{self.array.address_label()} {self.target}',
        ]
