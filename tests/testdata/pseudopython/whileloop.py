# type: ignore

i: int

i = 0

checkpoint(0)  # Reach

while i < 10:
    checkpoint(1)  # Reach 10 times
    i = i + 1

checkpoint(2)  # Reach
