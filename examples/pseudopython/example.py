# type: ignore

class B:
    i: int
    b: bool

class A:
    j: int
    pb: ptr[B]

a: A
b: B
a.pb = ref(b)

deref(a.pb).i = 42
deref(a.pb).b = True

assert_eq(b.i, 42)
assert_eq(b.b, True)
