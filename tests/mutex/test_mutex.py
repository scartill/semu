# type: ignore
import pytest

import semu.sasm.masm as masm
import semu.sasm.asm as asm
import semu.runtime.emulator as emulator
import semu.runtime.cpu as cpu

import unit_utils
from fixtures import with_kernel, with_hardware  # noqa: F401


def test_mutex(with_kernel, capsys):  # noqa: F811
    item = masm.collect_file(unit_utils.find_file('mutex/app.sasm'))
    binary = asm.compile_items(with_kernel + [item])

    with pytest.raises(cpu.Halt):
        emulator.execute(binary)

    with capsys.disabled():
        assert capsys.readouterr().out == unit_utils.load_file('mutex/output.log')
