from pathlib import Path
import logging as lg

import click

import semu.compile.mfpp as mfpp
import semu.compile.mgrammar as mgrammar


def namespace(src_filepath: Path) -> str:
    return src_filepath.stem


class CompilationItem:
    namespace: str
    contents: str


def collect_file(filename: str) -> CompilationItem:
    item = CompilationItem()
    path = Path(filename)
    item.contents = path.read_text()
    item.namespace = namespace(path)
    return item


def collect_files(filenames: list[str]) -> list[CompilationItem]:
    return [collect_file(in_filename) for in_filename in filenames]


def compile_items(compile_items: list[CompilationItem]) -> bytearray:
    # First pass
    first_pass = mfpp.MacroFPP()

    for compile_item in compile_items:
        lg.info("Processing {0}".format(compile_item.namespace))
        first_pass.namespace = compile_item.namespace
        actions = mgrammar.program.parse_string(compile_item.contents)

        for (func, arg) in actions:  # type: ignore
            func(first_pass, arg)

    # Second pass
    bytestr = bytearray()
    for (t, d) in first_pass.cmd_list:
        if t == 'bytes':
            bytestr += d

        if t == 'ref':
            (ref_offset, labelname) = d
            label_offset = first_pass.label_dict[labelname]
            offset = label_offset - ref_offset
            bytestr += struct.pack(">i", offset)

    # Dumping results
    return bytestr


def compile_files(in_filenames: list[str], out_filename: str):
    in_items = collect_files(in_filenames)
    bytestr = compile(in_items)
    Path(out_filename).write_bytes(bytestr)


@click.command()
@click.argument('sources', nargs=-1)
@click.argument('binary')
def compile(sources: list[str], binary: str):
    lg.basicConfig(level=lg.INFO)
    lg.info("SEMU ASM")
    compile_files(sources, binary)
