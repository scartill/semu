''' First-pass macroprocessor '''

import logging as lg
from typing import Dict, List

from semu.common.hwconf import WORD_SIZE
import semu.common.ops as ops
from semu.sasm.fpp import FPP, Tokens


class Context:
    ''' Abstract compilation context '''
    pass


# Default global context
class GlobalContext(Context):
    parent: Context

    def __init__(self):
        self.parent = self


# Struct definition
class Struct(Context):
    def __init__(self, name: str, parent: Context):
        self.parent = parent
        self.name = name
        self.fields: Dict[str, int] = dict()
        self.size: int = 0  # size in words

    def add_field(self, name: str, width: int):
        lg.debug(f'Field {name}:{width}:{self.size}')
        self.fields[name] = self.size
        self.size += width

    def get_offset(self, fieldname: str):
        return self.fields[fieldname] * WORD_SIZE  # offset in bytes


class Func(Context):
    locals: List[str]

    def __init__(self, name: str, parent: Context):
        self.parent = parent
        self.name = name
        self.locals = []


class MacroFPP(FPP):
    context: Context
    structs: Dict[str, Struct]
    consts: Dict[str, int]

    def __init__(self):
        FPP.__init__(self)
        self.context = GlobalContext()
        self.structs = dict()
        self.consts = dict()

    # Macros
    def issue_dw(self, tokens: Tokens):
        self.on_label(tokens[0])

        if len(tokens) == 2:
            multipicity = int(tokens[1])
        else:
            multipicity = 1

        for _ in range(multipicity):
            self.issue_usigned(0x00000000)

    # CALL <func-ref>
    # Invalidates 'h'
    def issue_call(self, tokens: Tokens):
        self.issue_op(ops.LDR)
        self.on_ref(tokens[0])
        self.on_reg(7)  # Using the last for routine address
        self.issue_op(ops.CLL)
        self.on_reg(7)

    # FUNC <func-name>
    def begin_func(self, tokens: Tokens):
        name = tokens[0]
        qname = self.get_qualified_name(name)

        if not isinstance(self.context, GlobalContext):
            raise Exception('Cannot define non-global FUNC {0}', qname)

        self.context = Func(name, self.context)
        self.on_label(name)  # Does nothing fancy really

    # Inside FUNC:
    #   DW <var-name> <init_reg>
    def func_var(self, tokens: Tokens):
        func = self.context

        if not isinstance(func, Func):
            raise Exception('Unable to define local variable outside a function')

        vname = str(tokens[0])
        reg = int(tokens[1])

        if vname in func.locals:
            raise Exception("Duplicate local variable declaration")

        func.locals.append(vname)

        # push <reg>
        self.issue_op(ops.PSH)
        self.on_reg(reg)

    # Inside FUNC:
    #   RETURN
    # Invalidates 'h'
    def func_return(self, tokens: Tokens):
        func = self.context

        if not isinstance(func, Func):
            raise Exception('Unexpected RETURN macro')

        # Go to <func-name>:epilogue
        pname = func.name + ':epilogue'

        # ldr &name:epilogue h
        self.issue_op(ops.LDR)
        self.on_ref([pname])
        self.on_reg(7)

        # jmp h
        self.issue_op(ops.JMP)
        self.on_reg(7)

    # Inside FUNC:
    #   END
    # Invalidates 'h'
    def end_func(self, tokens: Tokens):
        func = self.context

        if not isinstance(func, Func):
            raise Exception('Unexpected END macro')

        pname = func.name + ':epilogue'
        self.on_label(pname)

        # pop h
        # ...
        # pop h
        # ret
        for _ in func.locals:
            self.issue_op(ops.POP)
            self.on_reg(7)  # Dumping values to 'h'

        self.issue_op(ops.RET)

        # Restore global context
        self.context = func.parent

    # LSTORE <reg> <var-name>
    # Invalidates 'h'
    def local_store(self, tokens: Tokens):
        func = self.context

        if not isinstance(func, Func):
            raise Exception('Unexpected LSTORE macro')

        reg = tokens[0]
        vname = tokens[1]

        offset = func.locals.index(vname) * WORD_SIZE
        lg.debug(f'Local store {vname}@{offset}')

        # lla <var-offset> h
        # mrm <reg> h
        self.issue_op(ops.LLA)
        self.issue_usigned(offset)
        self.on_reg(7)
        self.issue_op(ops.MRM)
        self.on_reg(reg)
        self.on_reg(7)

    # LLOAD <var-name> <reg>
    # Invalidates 'h'
    def local_load(self, tokens: Tokens):
        func = self.context

        if not isinstance(func, Func):
            raise Exception('Unexpected LLOAD macro')

        vname = tokens[0]
        reg = tokens[1]

        offset = func.locals.index(vname) * WORD_SIZE
        lg.debug(f'Local load {vname}@{offset}')

        # lla <var-offset> h
        # mmr h <reg>
        self.issue_op(ops.LLA)
        self.issue_usigned(offset)
        self.on_reg(7)
        self.issue_op(ops.MMR)
        self.on_reg(7)
        self.on_reg(reg)

    # STRUCT <struct-type-name>
    def begin_struct(self, tokens: Tokens):
        name = tokens[0]
        qname = self.get_qualified_name(name)

        if not isinstance(self.context, GlobalContext):
            raise Exception('Cannot define non-global STRUCT type')

        self.context = Struct(qname, self.context)

    # DW <field-name>
    def struct_field(self, tokens: Tokens):
        type = tokens[0]
        fname = tokens[1]

        if type == 'DW':
            width = 1
        else:
            raise Exception(f'Bad type {type}')

        s = self.context

        if not isinstance(s, Struct):
            raise Exception('Unable to define STRUCT field outside a record')

        s.add_field(fname, width)

    # END
    def struct_end(self, tokens: Tokens):
        if not isinstance(self.context, Struct):
            raise Exception('Unable to define end STRUCT outside a record')

        s = self.context

        self.structs[s.name] = s
        self.context = s.parent
        lg.debug(f'Struct {s.name}')

    # DS <type-name> <array-name> [* <size>]
    def issue_ds(self, tokens: Tokens):
        qsname = self.resolve_name(tokens[0])
        s = self.structs[qsname]

        name = tokens[1]

        if len(tokens) == 3:
            multipicity = int(tokens[2])
        else:
            multipicity = 1

        words = s.size * multipicity
        self.on_label(name)

        # Issue placeholder-bytes
        for _ in range(words):
            self.issue_usigned(0x00000000)

    # PTR <struct-address-reg> <struct-type-name>#<field-name> <target-reg>
    # Invalidates 'g', 'h'
    def issue_ptr_head(self, tokens: Tokens):
        self.issue_op(ops.MRR)

    # Invalidates g, h
    def issue_ptr_tail(self, tokens: Tokens):
        # <before>: partial command to to load struct address to reg
        # for PTR: mrr source-reg
        fname = tokens[0]
        qsname = self.resolve_name(tokens[1])
        s = self.structs[qsname]
        offset = s.get_offset(fname)

        self.on_reg(7)  # Using the last ('h') for struct address
        self.issue_op(ops.LDC)  # Loading the offset
        self.issue_usigned(offset)
        self.on_reg(6)  # Using 'g' for field offset
        self.issue_op(ops.ADD)  # Adding the offset
        self.on_reg(7)
        self.on_reg(6)
        # <after>: target reg

    # ITEM <struct-type-name-name>
    # Parameters: 'a' - array address, 'b' - index
    # Invalidates a, b, h
    # Returns a - item address
    def issue_item(self, tokens: Tokens):
        # a - base
        # b - index
        qsname = self.resolve_name(tokens[0])
        s = self.structs[qsname]
        width = s.size * WORD_SIZE

        # ldc <size> h
        self.issue_op(ops.LDC)
        self.issue_usigned(width)
        self.on_reg(7)

        # mul b h b
        self.issue_op(ops.MUL)
        self.on_reg(1)
        self.on_reg(7)
        self.on_reg(1)

        # add a b a
        self.issue_op(ops.ADD)
        self.on_reg(0)
        self.on_reg(1)
        self.on_reg(0)

    # DT <text-name> "<string>"
    def issue_dt(self, tokens: Tokens):
        self.on_label(tokens[0])
        text = tokens[1]
        self.issue_usigned(len(text))

        for c in text.encode():
            self.issue_usigned(c)

    # CONST <name> <integer>
    def const_def(self, tokens: Tokens):
        name = tokens[0]
        value = int(tokens[1])  # Integer constants support
        qname = self.get_qualified_name(name)

        if not isinstance(self.context, GlobalContext):
            raise Exception('Cannot define non-global CONST {0}', qname)

        self.consts[qname] = value
        lg.debug("Constant {0}={1}".format(qname, value))

    # CLOAD <const-name> <reg>
    # Invalidates <reg>
    def const_load(self, tokens: Tokens):
        qsname = self.resolve_name(tokens[0])
        value = self.consts[qsname]
        reg = tokens[1]
        # ldc <const> <reg>
        self.issue_op(ops.LDC)
        self.issue_usigned(value)
        self.on_reg(reg)
