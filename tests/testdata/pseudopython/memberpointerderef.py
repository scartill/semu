# type: ignore

class C:
    i: int
    b: bool

c: C

c.i = 42
c.b = True

pc: ptr[C]
pc = ref(c)

j: int
j = pc.i

assert_eq(j, 42)

b: bool
b = pc.b
assert_eq(b, True)

def foo(pj: ptr[C]):
    j: int
    j = pj.i
    assert_eq(j, 42)
    b: bool
    b = pj.b
    assert_eq(b, True)

foo(pc)
