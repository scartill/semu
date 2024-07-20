from typing import Literal

type Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']


def checkpoint(label: int) -> str:
    return f'.check {label}'


def assertion(key: Register, value: int) -> str:
    return f'.assert {key} {value}'
