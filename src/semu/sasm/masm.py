from pathlib import Path
import logging as lg
from typing import Tuple, List
import tomllib

import click

from semu.sasm.asm import CompilationItem, compile_items
import semu.sasm.hwc as hwc


def collect_file(filepath: str | Path) -> CompilationItem:
    if isinstance(filepath, str):
        filepath = Path(filepath)

    lg.debug(f'Collecting file {filepath}')
    item = CompilationItem()
    item.contents = filepath.read_text()
    item.modulename = filepath.stem
    return item


def collect_files(filepaths: list[Path]) -> list[CompilationItem]:
    return [collect_file(path) for path in filepaths]


def collect_library(lib_dir: Path):
    libfile_path = lib_dir / Path('library.toml')
    config = tomllib.loads(libfile_path.read_text())
    library = config['library']

    items = [
        collect_file(lib_dir / Path(source)).set_package(library['package'])
        for source in library['sources']
    ]

    return items


@click.command()
@click.option('-v', '--verbose', is_flag=True, help='Sets logging level to debug')
@click.option('--hw', is_flag=True, help='Add hardware definitions', default=True)
@click.option('-l', '--library', type=click.Path())
@click.argument('sources', nargs=-1, type=Path)
@click.argument('binary', type=Path)
def compile(verbose: bool, hw: bool, library: Path, sources: Tuple[Path], binary: Path):
    lg.basicConfig(level=lg.DEBUG if verbose else lg.INFO)
    lg.info("SEMU ASM")

    items: List[CompilationItem] = []

    if hw:
        lg.info('Adding harware definitions')
        items.append(hwc.generate_compilation_item())

    if library:
        items.extend(collect_library(library))

    items.extend(collect_files(list(sources)))
    bytestr = compile_items(items)
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(bytestr)


if __name__ == "__main__":
    compile()
