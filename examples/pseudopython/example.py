# type: ignore

class A:
    i: int
    b: bool

    def foo():
        checkpoint(0)


A.foo()
