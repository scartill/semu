# type: ignore

# pf: fun[[int, int], bool]

def is_greater_than(a: int, b: int) -> bool:
    return a > b

b: bool
b = is_greater_than(1, 2)
assert_eq(b, False)
