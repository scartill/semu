# type: ignore

a: int
pa: ptr[int]
pb: ptr[int]
pc: ptr[int]

a = 42

pa = ref(a)
pb = ref(a)
pc = pa

assert_eq(a, 42)
assert_eq(deref(pa), 42)
assert_eq(deref(pb), 42)
assert_eq(deref(pc), 42)

a = 43

assert_eq(a, 43)
assert_eq(deref(pa), 43)
assert_eq(deref(pb), 43)
assert_eq(deref(pc), 43)

refset(pa, 44)

assert_eq(a, 44)
assert_eq(deref(pa), 44)
assert_eq(deref(pb), 44)
assert_eq(deref(pc), 44)

refset(pc, 45)

assert_eq(a, 45)
assert_eq(deref(pa), 45)
assert_eq(deref(pb), 45)
assert_eq(deref(pc), 45)
