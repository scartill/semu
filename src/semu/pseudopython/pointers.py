from typing import Sequence

import semu.pseudopython.registers as regs
import semu.pseudopython.pptypes as t
import semu.pseudopython.names as n
import semu.pseudopython.elements as el
import semu.pseudopython.classes as cls


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


class MethodPointerOperatorType(el.BuiltinMetaoperator):
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


class MethodPointerType(t.AbstractCallableType):
    class_type: cls.Class
    arg_types: t.PhysicalTypes
    return_type: t.PhysicalType

    def __init__(
        self, class_type: cls.Class,
        arg_types: t.PhysicalTypes, return_type: t.PhysicalType
    ):
        super().__init__()
        self.class_type = class_type
        self.arg_types = arg_types
        self.return_type = return_type

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, MethodPointerType):
            return False

        return (
            self.class_type == o.class_type
            and self.arg_types == o.arg_types
            and self.return_type == o.return_type
        )

    def __str__(self) -> str:
        return (
            f'<{self.class_type.name}::'
            f'{", ".join(str(e) for e in self.arg_types)} -> {self.return_type}>'
        )

    def json(self):
        data = super().json()
        data.update({
            'Class': 'MethodPointerType',
            'argTypes': [e.json() for e in self.arg_types],
            'ReturnType': self.return_type.json()
        })
        return data


PointerOperator = PointerOperatorType()
FunctionPointerOperator = FunctionPointerOperatorType()
MethodPointerOperator = MethodPointerOperatorType()
