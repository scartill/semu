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
