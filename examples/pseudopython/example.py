# type: ignore

class C:
    i: int
    b: bool

c: C
c.i = 42
c.b = True

j: int
j = c.i
assert_eq(j, 42)

bb: bool
bb = c.b
assert_eq(bb, True)
