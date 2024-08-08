# type: ignore

a: int
b: int

SERIAL_MM_BASE is 64
AnotherConstant is 128

a = 1
b = SERIAL_MM_BASE

c: int
c = a

assert_eq(1, 1)
assert_eq(a, 1)
assert_eq(b, SERIAL_MM_BASE)
assert_eq(c, 1)
assert_eq(AnotherConstant, 128)
