from typing import List, Set, Literal


Register = Literal['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'void']
REGISTERS: List[Register] = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
NUMBER_OF_REGISTERS = len(REGISTERS)
DEFAULT_REGISTER = 'a'
VOID_REGISTER = 'void'
Available = Set[Register]


def get_available(used: List[Register]) -> Available:
    available = set(REGISTERS.copy())
    available.difference_update(used)
    return available


def get_temp(used: List[Register]) -> Register:
    available = get_available(used)
    temp = available.pop()
    return temp
