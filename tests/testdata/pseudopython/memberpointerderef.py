# type: ignore

class C:
    i: int
    b: bool

c: C

c.i = 42
c.b = True

pc: ptr[C]
pc = c

j: int
j = deref(pc.i)

assert_eq(j, 42)
