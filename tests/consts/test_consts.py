import pytest

import semu.sasm.asm as asm
import semu.runtime.emulator as emulator
import semu.runtime.cpu as cpu

import unit_utils


def test_consts():
    item = asm.CompilationItem()
    item.namespace = 'consts'
    item.contents = unit_utils.load_file('consts/consts.sasm')
    binary = asm.compile_items([item])

    with pytest.raises(cpu.Halt):
        emulator.execute(binary)
