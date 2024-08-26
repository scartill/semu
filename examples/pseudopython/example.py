# type: ignore

FORTY_TWO is 42

j: int
j = 101

class C:
    i: int
    b: bool

    def foo():
        assert_eq(j, 101)

c: C
c.i = FORTY_TWO
c.b = True

assert_eq(c.i, 42)
assert_eq(c.b, True)

c.foo()
