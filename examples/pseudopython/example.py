# type: ignore

a: int
pa: ptr[int]

a = 1

pa = a

b: int
b = deref(pa)

assert_eq(b, 1)

# deref(pa) = 2