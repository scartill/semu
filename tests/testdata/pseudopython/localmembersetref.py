# type: ignore
class C:
    b: bool
    i: int

c: C

c.b = True
c.i = 42

pc: ptr[C]
pc = c

assert_eq(bool_to_int(pc.b), 1)
assert_eq(pc.i, 42)

def change(pc: ptr[C], k: int, v: bool):
    pc.i = k
    pc.b = v

change(pc, 101, False)
assert_eq(bool_to_int(pc.b), 0)
assert_eq(pc.i, 101)

change(c, 404, True)
assert_eq(bool_to_int(pc.b), 1)
assert_eq(pc.i, 404)
