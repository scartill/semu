# type: ignore

a: int
a = 1 + 2
std.assert_eq(a, 3)

b: int
b = a - 2
std.assert_eq(b, 1)

a = a - b
std.assert_eq(a, 2)

b = 3 * a
std.assert_eq(b, 6)
