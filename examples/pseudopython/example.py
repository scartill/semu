# type: ignore

class A:
    i: int

    @staticmethod
    def static():
        checkpoint(2)

    def method_a():
        checkpoint(1)
        assert_eq(this.i, 1)

    def method_b():
        checkpoint(0)
        static()
        this.method_a()

a: A
a.i = 1

A.static()
a.method_b()
