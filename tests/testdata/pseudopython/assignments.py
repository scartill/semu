# type: ignore

a: int
b: int

SERIAL_MM_BASE is 64
AnotherConstant is 128

a = 1
b = SERIAL_MM_BASE

c: int
c = a

std.assert_eq(1, 1)
std.assert_eq(a, 1)
std.assert_eq(b, SERIAL_MM_BASE)
std.assert_eq(c, 1)
std.assert_eq(AnotherConstant, 128)
