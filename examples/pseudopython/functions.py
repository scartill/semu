# type: ignore

def foo():
    pass

checkpoint(0)

def test():
    checkpoint(1)

test()
test()
test()

checkpoint(2)
