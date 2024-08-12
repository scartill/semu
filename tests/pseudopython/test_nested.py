import pytest

import semu.pseudopython.helpers as h
import semu.pseudopython.compiler as compiler

import semu.sasm.asm as asm
import semu.runtime.emulator as emulator
import semu.runtime.cpu as cpu

from unit_utils import find_file, load_file


def test_nested(capsys):
    with pytest.raises(cpu.Halt):
        pyroot = find_file('testdata/pseudopython/nested')
        main = pyroot / 'main.py'
        pp_path = str(pyroot.resolve())
        settings = h.CompileSettings().update(verbose=True, pp_path=pp_path)
        pysource = main.read_text()
        namespace = 'main'
        sasm = compiler.compile_string(settings, namespace, pysource)
        item = asm.CompilationItem()
        item.modulename = namespace
        item.contents = sasm
        binary = asm.compile_items([item])
        emulator.execute(binary)

    with capsys.disabled():
        output = load_file('testdata/pseudopython/nested/output.log')
        assert capsys.readouterr().out == output
