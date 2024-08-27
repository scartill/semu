from typing import Sequence

from semu.pseudopython.flatten import flatten
import semu.pseudopython.registers as regs
import semu.pseudopython.base as b
import semu.pseudopython.pptypes as t
import semu.pseudopython.expressions as ex


class PointerToGlobal(ex.PhyExpression):
    known_name: b.KnownName

    def __init__(
        self, known_name: b.KnownName,
        target: regs.Register = regs.DEFAULT_REGISTER,
        pp_type: t.PointerType | None = None
    ):
        if pp_type is None:
            assert isinstance(known_name.pp_type, t.PhysicalType)
            pp_type = t.PointerType(known_name.pp_type)

        super().__init__(pp_type, target)
        self.known_name = known_name

    def json(self):
        data = ex.Expression.json(self)
        data.update({'PointerToGlobal': self.known_name.name})
        return data

    def emit(self):
        label = self.known_name.address_label()

        return [
            f'ldr &{label} {self.target}',
            f'// ^ Loading global pointer to {self.known_name.name}'
        ]


class PointerToLocal(ex.PhyExpression):
    variable: ex.StackVariable

    def __init__(
        self, variable: ex.StackVariable,
        target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(variable.pp_type, t.PhysicalType)
        pp_type = t.PointerType(variable.pp_type)
        super().__init__(pp_type, target)
        self.variable = variable

    def json(self):
        data = super().json()
        data['Class'] = 'StackVariableLoad'
        data['Variable'] = self.variable.name
        return data

    def emit(self):
        available = regs.get_available([self.target])
        temp_offset = available.pop()
        offset = self.variable.offset

        return [
            f'// Loading stack variable at offset:{offset}',
            f'ldc {offset} {temp_offset}',
            f'lla {temp_offset} {self.target}'
        ]


class PointerOperatorType(ex.BuiltinMetaoperator):
    def __init__(self):
        super().__init__('ptr')


class FunctionPointerOperatorType(ex.BuiltinMetaoperator):
    def __init__(self):
        super().__init__('fun')

    def json(self):
        data = super().json()
        data['Class'] = 'FunctionPointerOperatorType'
        return data


class MethodPointerOperatorType(ex.BuiltinMetaoperator):
    def __init__(self):
        super().__init__('method')

    def json(self):
        data = super().json()
        data['Class'] = 'MethodPointerOperatorType'
        return data


class FunctionPointerType(t.AbstractCallableType):
    arg_types: Sequence[t.PhysicalType]
    return_type: t.PhysicalType

    def __init__(self, arg_types: t.PhysicalTypes, return_type: t.PhysicalType):
        super().__init__()
        self.arg_types = arg_types
        self.return_type = return_type

    def __str__(self) -> str:
        return f'<{", ".join(str(e) for e in self.arg_types)} -> {self.return_type}>'

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, FunctionPointerType):
            return False

        return self.arg_types == o.arg_types and self.return_type == o.return_type

    def json(self):
        data = super().json()
        data.update({
            'Class': 'FunctionPointerType',
            'ArgTypes': [str(e) for e in self.arg_types],
            'ReturnType': str(self.return_type)
        })
        return data


class Deref(ex.PhyExpression):
    source: ex.PhyExpression

    def __init__(
        self, source: ex.PhyExpression, target: regs.Register = regs.DEFAULT_REGISTER
    ):
        assert isinstance(source.pp_type, t.PointerType)
        super().__init__(source.pp_type.ref_type, target)
        self.source = source

    def json(self):
        data = ex.Expression.json(self)
        data.update({'DerefOf': self.pp_type.json()})
        return data

    def emit(self) -> ex.Sequence[str]:
        assert isinstance(self.pp_type, t.PhysicalType)

        return flatten([
            f'// Being dereference (pointer type: {self.pp_type})',
            self.source.emit(),
            '// ^ Calculate the address',
            f'mmr {self.source.target} {self.target}',
            '// ^ Do the dereference',
            '// End dereference'
        ])


PointerOperator = PointerOperatorType()
FunctionPointerOperator = FunctionPointerOperatorType()
MethodPointerOperator = MethodPointerOperatorType()
