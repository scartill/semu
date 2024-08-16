import semu.pseudopython.base as b
import semu.pseudopython.names as n


class ModuleType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Module'})
        return data


class PackageType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Package'})
        return data


class CallableType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Callable'})  # TODO: Add more information
        return data


class ClassType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Class'})
        return data


class NamedType(b.TargetType, n.KnownName):
    def __init__(self, name: str, namespace: n.INamespace | None = None):
        b.TargetType.__init__(self)
        n.KnownName.__init__(self, namespace, name, b.Builtin)

    def json(self):
        data: b.JSON = {'Class': 'NamedType'}
        data['TargetType'] = b.TargetType.json(self)
        data['KnownName'] = n.KnownName.json(self)
        return data

    def __str__(self) -> str:
        return self.name


class UnitType(NamedType):
    def __init__(self):
        super().__init__('unit')

    def json(self):
        data = super().json()
        data.update({'Class': 'UnitType', 'Builtin': 'unit'})
        return data


class DecoratorType(NamedType):
    def __init__(self, name: str, namespace: n.INamespace):
        super().__init__(name, namespace)

    def json(self):
        data = super().json()
        data.update({'Class': 'DecoratorType'})
        return data


class PhysicalType(NamedType):
    def __init__(self, name: str):
        super().__init__(name)


class Int32Type(PhysicalType):
    def __init__(self):
        super().__init__('int')

    def __str__(self):
        return 'int32'

    def json(self):
        data = super().json()
        data.update({'Class': 'Int32Type', 'Builtin': 'int32'})
        return data


class Bool32Type(PhysicalType):
    def __init__(self):
        super().__init__('bool')

    def __str__(self):
        return 'bool32'

    def json(self):
        data = super().json()
        data.update({'Class': 'Bool32Type', 'Builtin': 'bool32'})
        return data


class AbstractPointerType(NamedType):
    def __init__(self):
        super().__init__('pointer')

    def json(self):
        data = super().json()
        data.update({'Class': 'AbstractPointerType', 'Builtin': 'pointer'})
        return data


class PointerType(PhysicalType):
    ref_type: PhysicalType

    def __init__(self, ref_type: PhysicalType):
        super().__init__('pointer')
        self.ref_type = ref_type

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PointerType):
            return False

        return self.ref_type == value.ref_type

    def name(self):
        return f'pointer<{self.target_type}>'

    def json(self):
        data = super().json()
        data['Class'] = 'PointerType'
        data['RefType'] = str(self.ref_type)
        return data


Module = ModuleType()
Package = PackageType()
Class = ClassType()
Callable = CallableType()

Unit = UnitType()
Int32 = Int32Type()
Bool32 = Bool32Type()
AbstractPointer = AbstractPointerType()
AbstractPhysical = PhysicalType('physical')
