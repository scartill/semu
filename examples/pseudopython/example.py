# type: ignore

class C:
    i: int
    b: bool

    def foo():
        pass

c: C
c.i = 1
c.b = True

assert_eq(c.i, 1)
assert_eq(c.b, True)
