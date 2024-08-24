from typing import Sequence

import semu.pseudopython.base as b


class ModuleType(b.PPType):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return 'module'

    def json(self):
        data = super().json()
        data.update({'Class': 'ModuleType'})
        return data


class PackageType(b.PPType):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return 'package'

    def json(self):
        data = super().json()
        data.update({'Class': 'PackageType'})
        return data


class ClassType(b.PPType):
    def __init__(self):
        super().__init__()

    def __str__(self):
        return 'class'

    def json(self):
        data = super().json()
        data.update({'Class': 'ClassType'})
        return data


class UnitType(b.PPType, b.KnownName):
    def __init__(self):
        b.PPType.__init__(self)
        b.KnownName.__init__(self, None, 'unit', b.Builtin)

    def json(self):
        data = super().json()
        data.update({'Class': 'UnitType', 'Builtin': 'unit'})
        return data


class DecoratorType(b.PPType, b.KnownName):
    def __init__(self, parent: b.INamespace, name: str):
        b.PPType.__init__(self)
        b.KnownName.__init__(self, parent, name, b.Builtin)

    def json(self):
        data = super().json()
        data.update({'Class': 'DecoratorType'})
        return data


class PhysicalType(b.PPType):
    def __init__(self):
        b.PPType.__init__(self)

    def __str__(self) -> str:
        return f'type:{self.json()["Class"]}'

    def json(self):
        data = super().json()
        data.update({'Class': 'PhysicalType'})
        return data


type PhysicalTypes = Sequence[PhysicalType]


class Int32Type(PhysicalType, b.KnownName):
    def __init__(self):
        PhysicalType.__init__(self)
        b.KnownName.__init__(self, None, 'int', b.Builtin)

    def __str__(self):
        return 'int32'

    def json(self):
        data = super().json()
        data['Class'] = 'Int32Type'
        data['KnownName'] = b.KnownName.json(self)
        data['PhysicalType'] = PhysicalType.json(self)
        return data


class Bool32Type(PhysicalType, b.KnownName):
    def __init__(self):
        PhysicalType.__init__(self)
        b.KnownName.__init__(self, None, 'bool', b.Builtin)

    def __str__(self):
        return 'bool32'

    def json(self):
        data = super().json()
        data['Class'] = 'Bool32Type'
        data['KnownName'] = b.KnownName.json(self)
        data['PhysicalType'] = PhysicalType.json(self)
        return data


class AbstractPointerType(PhysicalType, b.KnownName):
    def __init__(self):
        PhysicalType.__init__(self)
        b.KnownName.__init__(self, None, 'pointer', b.Builtin)

    def json(self):
        data = super().json()
        data['Class'] = 'AbstractPointerType'
        data['KnownName'] = b.KnownName.json(self)
        data['PhysicalType'] = PhysicalType.json(self)
        return data


class AbstractCallableType(PhysicalType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data['Class'] = 'AbstractCallableType'
        return data


class BuiltinCallableType(AbstractCallableType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data['Class'] = 'BuiltinCallableType'
        return data


class PointerType(PhysicalType):
    ref_type: PhysicalType

    def __init__(self, ref_type: PhysicalType):
        super().__init__()
        self.ref_type = ref_type

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PointerType):
            return False

        return self.ref_type == value.ref_type

    def __str__(self):
        return f'pointer<{self.ref_type}>'

    def json(self):
        data = super().json()
        data['Class'] = 'PointerType'
        data['RefType'] = str(self.ref_type)
        return data


# class CompoundType()


Module = ModuleType()
Package = PackageType()
Class = ClassType()

Unit = UnitType()
Int32 = Int32Type()
Bool32 = Bool32Type()
AbstractPointer = AbstractPointerType()
AbstractPhysical = PhysicalType()
BuiltinCallable = BuiltinCallableType()
AbstractCallable = AbstractCallableType()
