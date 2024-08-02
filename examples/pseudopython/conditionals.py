# type: ignore

a: bool

a = False

if a:
    std.checkpoint(0)  # No reach
else:
    std.checkpoint(1)  # Reach

if not a:
    std.checkpoint(2)  # Reach
else:
    std.checkpoint(3)  # No reach

i: int

i = 1

if i > 2:
    std.checkpoint(4)   # No reach

if i > 0:
    std.checkpoint(5)   # Reach

if i >= 1:
    std.checkpoint(6)   # Reach

if i >= 2:
    std.checkpoint(7)   # No reach

if i < 2:
    std.checkpoint(8)   # Reach
else:
    std.checkpoint(9)   # No reach

if i <= 1:
    std.checkpoint(10)  # Reach
else:
    std.checkpoint(11)  # No reach

# while i < 10:
#     i = i + 1
#     std.checkpoint(4)

# std.checkpoint(5)
