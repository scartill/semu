# type: ignore

b: int
b = 10

TWELVE is 12
TWENTY is 20

def test_int() -> int:
    return b + TWELVE + TWENTY
    
assert_eq(test_int(), 42)
