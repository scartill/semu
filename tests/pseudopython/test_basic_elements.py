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


def test_basicclasses(capsys):
    simple_with_capture('basicclasses', capsys)


def test_globalpointers():
    simple_test('globalpointers')


def test_moreglobalpointers():
    simple_test('moreglobalpointers')


def test_localpointers(capsys):
    simple_with_capture('localpointers', capsys)


def test_memberpointerderef():
    simple_test('memberpointerderef')


def test_stackmembersderef(capsys):
    simple_with_capture('stackmembersderef', capsys)


def test_localmembersetref():
    simple_test('localmembersetref')


def test_simplethis(capsys):
    simple_with_capture('simplethis', capsys)


def test_recussivemethods(capsys):
    simple_with_capture('recussivemethods', capsys)


def test_boolassert():
    simple_test('boolassert')


def test_funcpointer():
    simple_test('funcpointer')


def test_boundmethodcall():
    simple_test('boundmethodcall')


def test_unboundmethodcall():
    simple_test('unboundmethodcall')
