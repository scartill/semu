# type: ignore

def foo():
    pass

foo()

checkpoint(0)

def test():
    checkpoint(1)

test()
test()

checkpoint(2)
