# type: ignore

class C:
    def method_a():
        checkpoint(0)

    def method_b():
        checkpoint(1)
        method_a()


c: C
c.method_b()
