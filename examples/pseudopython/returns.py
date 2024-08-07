# type: ignore

def test_unit():
    checkpoint(1)
    return
    checkpoint(2)  # No reach

test_unit()
