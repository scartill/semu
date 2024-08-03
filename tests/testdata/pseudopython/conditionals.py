# type: ignore

a: bool

a = False

if a:
    checkpoint(0)  # No reach
else:
    checkpoint(1)  # Reach

if not a:
    checkpoint(2)  # Reach
else:
    checkpoint(3)  # No reach

i: int

i = 1

if i > 2:
    checkpoint(4)   # No reach

if i > 0:
    checkpoint(5)   # Reach

if i >= 1:
    checkpoint(6)   # Reach

if i >= 2:
    checkpoint(7)   # No reach

if i < 2:
    checkpoint(8)   # Reach
else:
    checkpoint(9)   # No reach

if i <= 1:
    checkpoint(10)  # Reach
else:
    checkpoint(11)  # No reach

if i == 1:
    checkpoint(12)  # Reach

if i != 1:
    checkpoint(13)  # No reach

if i == 0:
    checkpoint(14)  # No reach

j: int

j = 3

if i == 1 and j == 3:
    checkpoint(15)  # Reach

if i != 1 or j == 3:
    checkpoint(16)  # Reach
