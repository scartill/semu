import pytest

import semu.compile.asm as asm
import semu.runtime.emulator as emulator
import semu.runtime.cpu as cpu

import unit_utils


def test_locals():
    item = asm.CompilationItem()
    item.namespace = 'locals'
    item.contents = unit_utils.load_sasm('locals/locals.sasm')
    binary = asm.compile_items([item])

    with pytest.raises(cpu.Halt):
        emulator.execute(binary)
