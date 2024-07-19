# type: ignore
import pytest

import semu.compile.compiler as compiler
import semu.compile.asm as asm
import semu.runtime.emulator as emulator
import semu.runtime.cpu as cpu

import unit_utils
from fixtures import with_kernel, with_hardware


def test_mutex(with_kernel, capsys):
    item = compiler.collect_file(unit_utils.find_file('mutex/app.sasm'))
    binary = asm.compile_items(with_kernel + [item])

    with pytest.raises(cpu.Halt):
        emulator.execute(binary)

    with capsys.disabled():
        assert capsys.readouterr().out == unit_utils.load_file('mutex/output.log')
