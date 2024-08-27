# type: ignore

class C:
    i: int

    def get_forty_two() -> int:
        return 42

    def is_greater_than(a: int) -> bool:
        return a > this.b

c: C
c.i = 101

ft: int
ft = c.get_forty_two()
assert_eq(ft, 42)

# b: bool
# b = c.is_greater_than(1)
# assert_eq(b, False)

# pf: method[C, [int], bool]
# pf = C.is_greater_than


# b = pf(ref(c), 3)
# assert_eq(b, True)

# b = pf(ref(c), 1)
# assert_eq(b, False)
