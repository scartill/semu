# type: ignore

stdlib.checkpoint(1)
pass

a: int
b: int

SERIAL_MM_BASE = 64
a = 1
b = SERIAL_MM_BASE

c: int
c = a

stdlib.assertion(1, 1)
stdlib.assertion(a, 1)
stdlib.assertion(b, SERIAL_MM_BASE)
stdlib.assertion(c, 1)
