# type: ignore

class A:
    i: int
    b: bool

a: A
a.i = 1
a.b = True

assert_eq(a.i, 1)
