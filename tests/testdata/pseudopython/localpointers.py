# type: ignore

def foo(pa: ptr[int], b: int, c: bool):
    a: int
    a = deref(pa)
    assert_eq(a, 1)

    pc: ptr[int]
    pc = pa
    assert_eq(deref(pc), 1)

    refset(pa, 21 + b)

    if c:
        checkpoint(0)
    else:
        checkpoint(1)

a: int
a = 1

b: int
b = 21

pa: ptr[a]
pa = a

assert_eq(a, 1)
foo(pa, 21, True)
assert_eq(a, 42)
