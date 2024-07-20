# type: ignore
import semu.pysemu.stdlib as stdlib


def test(key, value):
    stdlib.checkpoint(1)
    stdlib.assertion('a', 1)


test(1)
