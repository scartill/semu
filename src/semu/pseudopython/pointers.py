import semu.pseudopython.registers as regs
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el


class PointerToGlobal(el.PhysicalExpression):
    known_name: n.KnownName

    def __init__(self, known_name: n.KnownName, target: regs.Register):
        assert isinstance(known_name.target_type, t.PhysicalType)
        super().__init__(t.PointerType(known_name.target_type), target)
        self.known_name = known_name

    def json(self):
        data = el.Expression.json(self)
        data.update({'PointerToGlobal': self.known_name.name})
        return data

    def emit(self):
        label = self.known_name.address_label()

        return [
            f'// Loading global pointer to {self.known_name.name}',
            f'ldr &{label} {self.target}'
        ]


class PointerOperatorType(el.BuiltinMetaoperator):
    def __init__(self):
        super().__init__('ptr')


class FunctionPointerOperatorType(el.BuiltinMetaoperator):
    def __init__(self):
        super().__init__('fun')

    def json(self):
        data = super().json()
        data['Class'] = 'FunctionPointerOperatorType'
        return data


PointerOperator = PointerOperatorType()
FunctionPointerOperator = FunctionPointerOperatorType()
