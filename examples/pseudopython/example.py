# type: ignore

class C:
    b: bool
    i: int

c: C

c.b = True
c.i = 21

pc: ptr[C]
pc = c

def bar(po: ptr[C], k: int):
    j: int
    j = deref(po.i)
    j = j + k
    assert_eq(j, 42)

bar(pc, 21)
