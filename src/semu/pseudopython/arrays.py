from typing import List, cast

from semu.common.hwconf import WORD_SIZE
from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.expressions as el
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


class GlobalArray(b.Element, b.KnownName):
    items: List['Globals']

    def __init__(
        self, namespace: ns.Namespace, name: str, pp_type: ArrayType,
        items: List['Globals']
    ):
        b.Element.__init__(self)
        b.KnownName.__init__(self, namespace, name, pp_type)
        self.items = items

    def item_type(self) -> t.PhysicalType:
        return cast(ArrayType, self.pp_type).item_type

    def typelabel(self) -> str:
        return 'global_array'

    def json(self):
        data: b.JSON = {'Class': 'GlobalArray'}
        data['KnownName'] = b.KnownName.json(self)
        data['Element'] = b.Element.json(self)
        return data

    def emit(self):
        label = self.address_label()
        tt = self.pp_type
        assert isinstance(tt, ArrayType)

        return flatten([
            f'// Begin global array {self.name} of type {tt}',
            f'{label}:',                            # label
            [e.emit() for e in self.items],         # items
            f'// End global array {self.name}'
        ])


type Globals = el.GlobalVariable | cls.GlobalInstance | GlobalArray


class ArrayItemPointerLoad(el.PhyExpression):
    instance_load: el.PhyExpression
    index: el.PhyExpression

    def __init__(
        self,
        instance_load: el.PhyExpression, index: el.PhyExpression,
        target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(instance_load.pp_type, t.PointerType)
        instance_type = instance_load.pp_type.ref_type
        assert isinstance(instance_type, ArrayType)
        item_type = instance_type.item_type
        pp_type = t.PointerType(item_type)
        super().__init__(pp_type, target)
        self.instance_load = instance_load
        self.index = index

    def json(self):
        data = super().json()

        data.update({
            'Class': 'ArrayItemAssignor',
            'InstanceLoad': self.instance_load.json(),
            'Index': self.index.json()
        })

        return data

    def emit(self) -> b.Sequence[str]:
        available = regs.get_available([
            self.index.target,
            self.target
        ])

        address = available.pop()
        index = available.pop()
        offset = available.pop()

        return flatten([
            '// Global array item pointer load',
            '// Calculating index',
            self.index.emit(),
            f'push {self.index.target}',
            '// Calculating address',
            self.instance_load.emit(),
            f'mrr {self.instance_load.target} {address}',
            f'pop {index}',
            f'ldc {WORD_SIZE} {offset}',
            f'mul {index} {offset} {offset}',
            f'add {address} {offset} {address}',
            f'mrr {address} {self.target}',
            '// End array item pointer load'
        ])
