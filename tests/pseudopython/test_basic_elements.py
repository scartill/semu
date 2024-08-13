import pytest

import semu.runtime.cpu as cpu

from unit_utils import execute_single_pp_source, load_file


def simple_test(name: str):
    with pytest.raises(cpu.Halt):
        execute_single_pp_source(f'testdata/pseudopython/{name}.py')


def simple_with_capture(name: str, capsys):
    with pytest.raises(cpu.Halt):
        execute_single_pp_source(f'testdata/pseudopython/{name}.py')

    with capsys.disabled():
        output = load_file(f'testdata/pseudopython/{name}.log')
        assert capsys.readouterr().out == output


def test_expressions():
    simple_test('expressions')


def test_assignments():
    simple_test('assignments')


def test_booleans():
    simple_test('booleans')


def test_checkpoints(capsys):
    simple_with_capture('checkpoints', capsys)


def test_conditionals(capsys):
    simple_with_capture('conditionals', capsys)


def test_whileloop(capsys):
    simple_with_capture('whileloop', capsys)


def test_noparamfunctions(capsys):
    simple_with_capture('noparamfunctions', capsys)


def test_returns(capsys):
    simple_with_capture('returns', capsys)


def test_nameresolve():
    simple_test('nameresolve')


def test_funcparams():
    simple_test('funcparams')


def test_localvars():
    simple_test('localvars')


def test_nestedfunc():
    simple_test('nestedfunc')


def test_basicclasses(capsys):
    simple_with_capture('basicclasses', capsys)


def test_globalpointers():
    simple_test('globalpointers')
