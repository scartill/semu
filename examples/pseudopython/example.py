# type: ignore

class C:
    i: int
    b: bool

c: C

c.i = 42
c.b = True

pc: ptr[C]
pc = c

i: int
i = c.i

assert_eq(i, 42)

# j: int
# j = pc.j

# assert_eq(j, 42)
