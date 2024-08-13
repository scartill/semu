from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el


class Deref32(el.Expression):
    value: el.Expression

    def __init__(
            self, target_type: t.PhysicalType, value: el.Expression,
            target: regs.Register
    ):
        assert isinstance(value.target_type, t.PointerType)
        super().__init__(target_type, target)
        self.value = value

    def json(self):
        data = el.Expression.json(self)
        data.update({'DerefOf': self.target_type.json()})
        return data

    def emit(self) -> el.Sequence[str]:
        assert isinstance(self.target_type, t.PhysicalType)

        return flatten([
            f'// Pointer type: {self.target_type.name}',
            self.value.emit(),
            '// Dereference',
            f'mmr {self.value.target} {self.target}'
        ])


class GlobalPointer32(el.Expression):
    known_name: n.KnownName

    def __init__(self, known_name: n.KnownName, target: regs.Register):
        if not isinstance(known_name.target_type, t.PhysicalType):
            raise ValueError('GlobalPointer32 can only point to PhysicalType')

        super().__init__(t.PointerType(known_name.target_type), target)
        self.known_name = known_name

    def json(self):
        data = el.Expression.json(self)
        data.update({'GlobalPointerTo': self.known_name.name})
        return data

    def emit(self):
        label = self.known_name.address_label()

        return [
            f'// Loading global pointer to {self.known_name.name}',
            f'ldr &{label} {self.target}'
        ]


class PointerOperatorType(n.KnownName, el.Expression):
    def __init__(self):
        n.KnownName.__init__(self, None, 'ptr', b.Builtin)
        el.Expression.__init__(self, b.Builtin, regs.VOID_REGISTER)

    def json(self):
        data = n.KnownName.json(self)
        data.update({'Class': 'PointerConstructor'})
        return data


PointerOperator = PointerOperatorType()
