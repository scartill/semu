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
j = pc.j

assert_eq(j, 42)
