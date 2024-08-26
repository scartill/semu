# type: ignore

pf: fun[[int, int], bool]

def is_greater_than(a: int, b: int) -> bool:
    return a > b

pf = is_greater_than

b: bool
b = is_greater_than(1, 2)
assert_eq(b, False)

b = pf(2, 1)
assert_eq(b, True)
