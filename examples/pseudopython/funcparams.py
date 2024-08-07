# type: ignore

def test_unit():
    checkpoint(1)


def test_unit_return():
    checkpoint(2)
    return
    checkpoint(3)  # No reach


test_unit()
test_unit_return()
checkpoint(4)


def test_int() -> int:
    if True:
        return 10 + 12 + 20
    else:
        return 0


i: int
i = test_int()

assert_eq(i, 42)