# type: ignore

class C:
    b: bool
    i: int

c: C

c.b = True
c.i = 21

pc: ptr[C]
pc = c

def read(po: ptr[C], k: int):
    j: int
    j = deref(po.i)
    j = j + k
    assert_eq(j, 42)
    assert_eq(bool_to_int(deref(po.b)), 1)

# read(pc, 21)


# def change(pc: ptr[C]):
#     pc.b = False
