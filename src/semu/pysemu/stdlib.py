from typing import Literal

type UInt32 = int
type Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']


# def _regassert(key: Register, value: UInt32) -> str:
#     return f'.assert {key} {value}'


def checkpoint(label: UInt32) -> str:
    return f'.check {label}'
