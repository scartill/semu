# type: ignore

class C:
    i: int

c: C

c.i = 42

def foo(pj: ptr[C]):
    j: int
    j = pj.i
    assert_eq(j, 42)

foo(c)
