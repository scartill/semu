# type: ignore

i: int

a: bool
b: bool

a = True
b = False

a = not a
i = std.bool_to_int(a)
std.assert_eq(i, 0)

b = not b
i = std.bool_to_int(b)
std.assert_eq(i, 1)

# c: bool
# c = a and b or True

# i = std.bool_to_int(a)
# std.assert_eq(i, 1)

# i = std.bool_to_int(b)
# std.assert_eq(i, 0)

# i = std.bool_to_int(c)
# std.assert_sq(i, 1)
