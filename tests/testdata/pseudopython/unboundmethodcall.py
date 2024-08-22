# type: ignore

class C:
    i: int

    def method_a():
        checkpoint(0)
        assert_eq(this.i, 1)

    def method_b():
        checkpoint(1)
        assert_eq(this.i, 1)
        method_a()


c: C
c.i = 1
c.method_b()
