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

def foo(pj: ptr[int]):
    j: int
    j = pj
    assert_eq(j, 42)

pi: ptr[int]
pi = pc.i

foo(pi)
foo(pc.i)

def bar(pb: ptr[bool]):
    assert_eq(bool_to_int(pb), 1)

bar(pc.b)
