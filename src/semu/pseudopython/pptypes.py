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


class UnitType(NamedType):
    def __init__(self):
        super().__init__('unit')

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Unit'})
        return data


class DecoratorType(NamedType):
    def __init__(self, name: str, namespace: n.INamespace):
        super().__init__(name, namespace)

    def json(self):
        data = super().json()
        data.update({'Builtin': 'Decorator', 'Name': self.name})
        return data


class PhysicalType(NamedType):
    words: int

    def __init__(self, name: str, words: int):
        super().__init__(name)
        self.words = words


class Int32Type(PhysicalType):
    def __init__(self):
        super().__init__('int', 1)

    def __str__(self):
        return 'int32'

    def json(self):
        data = super().json()
        data.update({'Builtin': 'int32'})
        return data


class Bool32Type(PhysicalType):
    def __init__(self):
        super().__init__('bool', 1)

    def __str__(self):
        return 'bool32'

    def json(self):
        data = super().json()
        data.update({'Builtin': 'bool32'})
        return data


class PointerType(PhysicalType):
    ref_type: PhysicalType

    def __init__(self, ref_type: PhysicalType):
        super().__init__('pointer', 1)
        self.ref_type = ref_type

    def name(self):
        return f'pointer<{self.target_type}>'

    def json(self):
        data = super().json()
        data.update({'Builtin': 'pointer', 'TargetType': self.ref_type.json()})
        return data


class LateinitType(b.TargetType):
    def __init__(self):
        super().__init__()

    def json(self):
        data = super().json()
        data.update({'Class': 'Builtin'})
        return data


Module = ModuleType()
Package = PackageType()
Class = ClassType()
Callable = CallableType()

Unit = UnitType()
Int32 = Int32Type()
Bool32 = Bool32Type()
Lateinit = LateinitType()
