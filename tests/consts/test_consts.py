import semu.compile.asm as asm


SASM = '''
CONST SERIAL_MM_BASE 64
CLOAD SERIAL_MM_BASE a
mrr a b
.assert b 64
CLOAD consts::SERIAL_MM_BASE d
.assert d 64
hlt
'''


def test_consts():
    item = asm.CompilationItem()
    item.namespace = 'consts'
    item.contents = SASM

    binary = asm.compile_items([item])
    print(binary)
    assert False
