# type: ignore

import inner
import children.child

assert_eq(inner.foo(), 42)
checkpoint(0)
assert_eq(children.child.bar(), 101)
checkpoint(1)
