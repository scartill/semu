# type: ignore

class C:
    b: int

    def is_greater_than(a: int) -> bool:
        return a > this.b

pf: method[C, [int], bool]
pf = C.is_greater_than

c: C
c.b = 2

pc: ptr[C]
pc = c

b: bool
b = c.is_greater_than(1)
assert_eq(b, False)

b = pf(pc, 3)
assert_eq(b, True)

b = pf(pc, 1)
assert_eq(b, False)
