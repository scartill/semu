# type: ignore

i: int

i = 0

std.checkpoint(0)  # Reach

while i < 10:
    std.checkpoint(1)  # Reach 10 times
    i = i + 1

std.checkpoint(2)  # Reach
