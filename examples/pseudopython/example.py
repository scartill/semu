# type: ignore

def test_example(i: int):
    j: int
    checkpoint(0)
    j = i
    assert_eq(j, 42)


test_example(42)
