# type: ignore
class C:
    i: int

c: C
c.i = 42

pc: ptr[C]
pc = c

def change(pc: ptr[C]):
    pc.i = 101

change(pc)
assert_eq(pc.i, 101)
