import semu.pseudopython.pptypes as t
import semu.pseudopython.elements as el


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

    def __str__(self):
        return f'array<{self.item_type}, {self.length}>'

    def json(self):
        data = super().json()
        data['Class'] = 'ArrayType'
        data['ItemType'] = str(self.item_type)
        data['Length'] = self.length
