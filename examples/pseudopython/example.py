# type: ignore

class C:
    i: int
    b: bool

c: C

c.i = 42
c.b = True

pc: ptr[C]
pc = c

def bar(po: ptr[C]):
    j: int
    j = deref(po.i)
    assert_eq(j, 42)

bar(pc)
