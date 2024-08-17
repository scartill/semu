# type: ignore


class C:
    b: int

    def is_greater_than(a: int) -> bool:
        return a > this.b

pf: method[C, [int, int], bool]

# pf = C.is_greater_than

# c: C
# c.b = 2

# b: bool
# b = c.is_greater_than(1)
# assert_eq(b, False)

# b = pf(2, 1)
# assert_eq(b, True)
