import logging as lg
from typing import cast
import struct

import semu.compile.mfpp as mfpp
import semu.compile.mgrammar as mgrammar


class CompilationItem:
    namespace: str
    contents: str


def compile_items(compile_items: list[CompilationItem]) -> bytes:
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
        new_bytes = bytes()

        if t == 'bytes':
            new_bytes = d

        if t == 'ref':
            (ref_offset, labelname) = d
            label_offset = first_pass.label_dict[str(labelname)]
            offset = label_offset - ref_offset
            new_bytes = struct.pack(">i", offset)

        bytestr += cast(bytes, new_bytes)

    # Dumping results
    return bytes(bytestr)
