# type: ignore

def foo():
    i: int
    i = 0
    assert_eq(i, 0)

foo()
