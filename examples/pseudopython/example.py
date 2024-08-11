# type: ignore

def outer() -> int:
    def inner() -> bool:
        return True

    return 42

assert_eq(outer(), 42)
assert_eq(bool_to_int(outer.inner()), 0)
