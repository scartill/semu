# type: ignore

def foo(x: int):
    checkpoint(0)
    assert_eq(x, 1)

foo(1)
