# type: ignore

import inner
import children.child
import another.another

assert_eq(inner.foo(), 42)
checkpoint(0)
assert_eq(children.child.bar(), 101)
checkpoint(1)

import children.sibling

assert_eq(children.sibling.bar(), 102)
checkpoint(2)

import children.third.deep

assert_eq(children.third.deep.foo(), 103)
checkpoint(3)

assert_eq(another.another.another(), 104)
checkpoint(4)
