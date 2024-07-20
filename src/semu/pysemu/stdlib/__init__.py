from typing import Literal

type UInt32 = int
type Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']


def checkpoint(label: UInt32) -> str:
    return f'.check {label}'


def assertion(key: Register, value: UInt32) -> str:
    return f'.assert {key} {value}'
