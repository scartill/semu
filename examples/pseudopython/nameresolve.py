# type: ignore

b: int
b = 10

def test_int() -> int:
    return b + 12 + 20
    
assert_eq(test_int(), 42)
