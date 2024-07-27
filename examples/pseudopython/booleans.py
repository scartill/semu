# type: ignore

a: bool
b: bool

a = True
b = False

i: int
i = std.bool_to_int(a)
std.assert_eq(i, 1)
