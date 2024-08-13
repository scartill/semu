# type: ignore

class A:
    i: int
    b: bool

    @staticmethod
    def foo():
        checkpoint(0)

A.foo()

a: A
a.i = 1
a.b = True

assert_eq(a.i, 1)
assert_eq(bool_to_int(a.b), 1)

a.b = False
assert_eq(bool_to_int(a.b), 0)
