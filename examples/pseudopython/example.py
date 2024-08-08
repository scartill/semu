# type: ignore

def unit_function(a: int):
    assert_eq(a, 42)

unit_function(42)
    
def unit_function_2(a: int, b: int):
    assert_eq(a + b, 42)

unit_function(21, 21)

#     return a + b

# i: int
# i = 1

# assert_eq(add(i, 2), 3)
