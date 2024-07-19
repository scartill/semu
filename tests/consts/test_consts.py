import semu.compile.asm as asm
import semu.emulator as emulator

import unit_utils


def test_consts():
    item = asm.CompilationItem()
    item.namespace = 'consts'
    item.contents = unit_utils.load_sasm('consts/consts.sasm')
    binary = asm.compile_items([item])
    emulator.execute(bytes(binary))
