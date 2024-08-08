# type: ignore

a: int
a = 1 + 2
assert_eq(a, 3)

b: int
b = a - 2
assert_eq(b, 1)

a = a - b
assert_eq(a, 2)

b = 3 * a
assert_eq(b, 6)
