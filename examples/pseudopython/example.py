# type: ignore

class C:
    b: bool
    i: int

c: C

c.b = True
c.i = 42

pc: ptr[C]
pc = c

def read(po: ptr[C]):
    checkpoint(0)
    assert_eq(deref(po.i), 42)
    assert_eq(bool_to_int(deref(po.b)), 1)

read(pc)
read(c)


# def change(pc: ptr[C]):
#     pc.b = False
