# type: ignore

i: int

a: bool
b: bool

a = True
b = False

a = not a
i = bool_to_int(a)
assert_eq(i, 0)

b = not b
i = bool_to_int(b)
assert_eq(i, 1)

c: bool
c = a and True and True and True and b # or True
i = bool_to_int(c)
assert_eq(i, 0)

c = a and True and True and True and b or True
i = bool_to_int(c)
assert_eq(i, 1)

c = a and c or True
i = bool_to_int(c)
assert_eq(i, 1)

i = bool_to_int(a)
assert_eq(i, 0)

i = bool_to_int(b)
assert_eq(i, 1)
