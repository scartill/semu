import pyparsing as pp

import ops
from mfpp import MacroFPP as MFPP

from grammar import *

# Macros
multi = pp.Optional(pp.Suppress("*") + pp.Regex("[1-9][0-9]*"))
macro_dw = (pp.Suppress("DW") + id + multi).setParseAction(lambda r: (MFPP.macro_issue_dw, r))
macro_call = (pp.Suppress("CALL") + refname).setParseAction(lambda r: (MFPP.macro_issue_call, r))
macro_func = (pp.Suppress("FUNC") + id).setParseAction(lambda r: (MFPP.macro_issue_func, r))

# Macro-struct
struct_begin = (pp.Suppress("STRUCT") + id).setParseAction(lambda r: (MFPP.macro_begin_struct, r))
field_type = pp.Or(pp.Literal("DW"))
struct_field = (field_type + id).setParseAction(lambda r: (MFPP.macro_struct_field, r))
struct_end = pp.Suppress("END").setParseAction(lambda r: (MFPP.macro_struct_end, r))
macro_struct = struct_begin + pp.OneOrMore(struct_field) + struct_end

macro_ds = (pp.Suppress("DS") + refname + id + multi).setParseAction(lambda r: (MFPP.macro_issue_ds, r))

ptr_head = pp.Literal("PTR").setParseAction(lambda r: (MFPP.macro_issue_ptr_head, r))
rptr_head = pp.Literal("RPTR").setParseAction(lambda r: (MFPP.macro_issue_rptr_head, r))
ptr_tail = (id + pp.Suppress("#") + refname).setParseAction(lambda r: (MFPP.macro_issue_ptr_tail, r))
macro_ptr = ptr_head + reg + ptr_tail + reg
macro_rptr = rptr_head + reg + ptr_tail + reg

macro_item = (pp.Suppress("ITEM") + refname).setParseAction(lambda r: (MFPP.macro_issue_item, r))

macro_dt = (pp.Suppress("DT") + id + pp.QuotedString('"')).setParseAction(lambda r: (MFPP.macro_issue_dt, r))

# Fail on unknown command
unknown = pp.Regex(".+").setParseAction(lambda r: (MFPP.on_fail, r))

cmd = asm_cmd \
    ^ macro_dw \
    ^ macro_call \
    ^ macro_func \
    ^ macro_struct \
    ^ macro_ds \
    ^ macro_ptr \
    ^ macro_rptr \
    ^ macro_item \
    ^ macro_dt
    
statement = pp.Optional(label) + pp.Optional(comment) + cmd + pp.Optional(comment)
program = pp.ZeroOrMore(statement ^ comment ^ unknown)