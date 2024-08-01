# type: ignore

a: bool

a = False

if a:
    std.checkpoint(0)
else:
    std.checkpoint(1)

if not a:
    std.checkpoint(2)
else:
    std.checkpoint(3)

std.checkpoint(4)
