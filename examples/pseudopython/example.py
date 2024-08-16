# type: ignore

class A:
    i: int

    @staticmethod
    def static():
        checkpoint(0)

    def method_a():
        assert_eq(deref(this.i), 1)
        checkpoint(1)

    def method_b(b: bool):
        assert_eq(deref(this.i), 1)
        assert_eq(bool_to_int(b), 1)
        checkpoint(2)
        this.method_a()

a: A
a.i = 1

A.static()
A.method_a(a)
a.method_b(True)
