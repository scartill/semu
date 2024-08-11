from pathlib import Path

import semu.pseudopython.helpers as h
import semu.pseudopython.compiler as compiler

import semu.sasm.asm as asm
import semu.runtime.emulator as emulator


def find_file(filename: str) -> Path:
    return Path(__file__).parent / filename


def load_file(filename: str) -> str:
    return find_file(filename).read_text()


def execute_single_pp_source(filename):
    settings = h.CompileSettings().update(verbose=True)
    pypath = find_file(filename)
    pysource = pypath.read_text()
    namespace = pypath.stem
    items = compiler.compile_single_string(settings, namespace, pysource)
    binary = asm.compile_items(items)
    emulator.execute(binary)
