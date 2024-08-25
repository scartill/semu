# type: ignore

FORTY_TWO is 42

class C:
    i: int
    b: bool

    def foo():
        pass

c: C
c.i = FORTY_TWO
c.b = True

assert_eq(c.i, 42)
assert_eq(c.b, True)
