# type: ignore

k: int
k = 1
assert_eq(k, 1)

ia: array[int, 3]
ia[0] = 11
ia[1] = 22
ia[2] = 33

inx: int
inx = 1
ia[inx + 1] = 44

# j: int
# j = ia[1]

# pja: ptr[array[int, 3]]
# pja = ia
