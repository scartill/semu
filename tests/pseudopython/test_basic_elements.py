import pytest

import semu.runtime.cpu as cpu

from unit_utils import execute_single_pp_source, load_file


def test_assignments():
    with pytest.raises(cpu.Halt):
        execute_single_pp_source('testdata/pseudopython/assignments.py')


def test_booleans():
    with pytest.raises(cpu.Halt):
        execute_single_pp_source('testdata/pseudopython/booleans.py')


def test_checkpoints(capsys):
    with pytest.raises(cpu.Halt):
        execute_single_pp_source('testdata/pseudopython/checkpoints.py')

    with capsys.disabled():
        output = load_file('testdata/pseudopython/checkpoints.log')
        assert capsys.readouterr().out == output


def test_conditionals(capsys):
    with pytest.raises(cpu.Halt):
        execute_single_pp_source('testdata/pseudopython/conditionals.py')

    with capsys.disabled():
        output = load_file('testdata/pseudopython/conditionals.log')
        assert capsys.readouterr().out == output
