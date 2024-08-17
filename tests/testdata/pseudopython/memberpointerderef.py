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
j = pc.i

assert_eq(j, 42)

def foo(pj: ptr[C]):
    j: int
    j = pj.i
    assert_eq(j, 42)

foo(pc)
