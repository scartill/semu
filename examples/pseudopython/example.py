# type: ignore

a: int
pa: ptr[int]

a = 1
pa = ref(a)

refset(pa, 2 + 3)
assert_eq(deref(pa), 5)
