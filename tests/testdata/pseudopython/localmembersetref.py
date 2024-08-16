# type: ignore

class C:
    b: bool
    i: int

c: C

c.b = True
c.i = 42

pc: ptr[C]
pc = c

assert_eq(bool_to_int(deref(pc.b)), 1)
assert_eq(deref(pc.i), 42)

def change(pc: ptr[C], k: int, v: bool):
    refset(pc.i, k)
    refset(pc.b, v)

change(pc, 101, False)
assert_eq(bool_to_int(deref(pc.b)), 0)
assert_eq(deref(pc.i), 101)

change(c, 404, True)
assert_eq(bool_to_int(deref(pc.b)), 1)
assert_eq(deref(pc.i), 404)
