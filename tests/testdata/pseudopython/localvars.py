# type: ignore

def local_int():
    x: int
    x = 42
    assert_eq(x, 42)

local_int()

def local_int_with_param(i: int):
    x: int
    x = 21
    assert_eq(x + i, 42)


local_int_with_param(21)

def local_int_with_param_and_return(i: int) -> int:
    x: int
    x = 21

    if x > 20:
        return x + i

r: int
r = local_int_with_param_and_return(21)
assert_eq(r, 42)
