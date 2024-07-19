import struct
import logging as lg
from typing import List, Tuple, Dict, Any

from semu.common.hwconf import WORD_SIZE

Tokens = List[Any]


class FPP:
    ''' First pass processor '''
    cmd_list: List[Tuple[str, bytes | Tuple[int, str]]]
    label_dict: Dict[str, int]

    def __init__(self):
        self.cmd_list = list()
        self.offset = 0
        self.namespace = "<global>"
        self.label_dict = dict()

    def get_qualified_name(self, name: str, namespace: str | None = None):
        if namespace is None:
            namespace = self.namespace

        qname = namespace + '::' + name
        return qname

    def resolve_name(self, tokens: Tokens):
        if len(tokens) == 1:
            # Unqualified
            name = self.get_qualified_name(tokens[0])
        else:
            # Qualified
            name = self.get_qualified_name(tokens[1], tokens[0])  # name, namespace

        return name

    # Handlers
    def issue_word(self, fmt: str, word: int):
        bytestr = struct.pack(fmt, word)
        self.cmd_list.append(('bytes', bytestr))
        self.offset += 4

    def issue_usigned(self, word: int):
        self.issue_word('>I', word)

    def issue_signed(self, word: int):
        self.issue_word('>i', word)

    def issue_op(self, op: int):
        lg.debug(f'Issuing command 0x{op:X}')
        self.issue_usigned(op)

    def on_uconst(self, tokens: Tokens):
        word = int(tokens[0])
        self.issue_usigned(word)

    def on_sconst(self, tokens: Tokens):
        word = int(tokens[0])
        self.issue_signed(word)

    def on_label(self, tokens: Tokens):
        labelname = tokens[0]
        qlabelname = self.get_qualified_name(labelname)
        self.label_dict[qlabelname] = self.offset
        lg.debug(f'Label {qlabelname} @ 0x{self.offset:X}')

    def on_reg(self, val: int):
        self.issue_usigned(val)

    def on_ref(self, refname: Tokens):
        labelname = self.resolve_name(refname)

        lg.debug(f'Ref {labelname}')

        self.cmd_list.append(('ref', (self.offset, labelname)))
        self.offset += WORD_SIZE  # placeholder-bytes

    def on_fail(self, rest: str):
        raise Exception(f'Unknown command {rest}')
