import pyparsing as pp

import ops
from mfpp import MacroFPP as MFPP

from grammar import *

# Macros
multi = pp.Optional(pp.Suppress("*") + pp.Regex("[1-9][0-9]*"))
dw = (pp.Suppress("DW") + id + multi).setParseAction(lambda r: (MFPP.issue_dw, r))
call = (pp.Suppress("CALL") + refname).setParseAction(lambda r: (MFPP.issue_call, r))

# Macro-struct
struct_begin = (pp.Suppress("STRUCT") + id).setParseAction(lambda r: (MFPP.begin_struct, r))
field_type = pp.Or(pp.Literal("DW"))
struct_field = (field_type + id).setParseAction(lambda r: (MFPP.struct_field, r))
struct_end = pp.Suppress("END").setParseAction(lambda r: (MFPP.struct_end, r))
struct = struct_begin + pp.OneOrMore(struct_field) + struct_end

ds = (pp.Suppress("DS") + refname + id + multi).setParseAction(lambda r: (MFPP.issue_ds, r))

ptr_head = pp.Literal("PTR").setParseAction(lambda r: (MFPP.issue_ptr_head, r))
rptr_head = pp.Literal("RPTR").setParseAction(lambda r: (MFPP.issue_rptr_head, r))
ptr_tail = (id + pp.Suppress("#") + refname).setParseAction(lambda r: (MFPP.issue_ptr_tail, r))
ptr = ptr_head + reg + ptr_tail + reg
rptr = rptr_head + reg + ptr_tail + reg

item = (pp.Suppress("ITEM") + refname).setParseAction(lambda r: (MFPP.issue_item, r))

dt = (pp.Suppress("DT") + id + pp.QuotedString('"')).setParseAction(lambda r: (MFPP.issue_dt, r))

# Fail on unknown command
unknown = pp.Regex(".+").setParseAction(lambda r: (MFPP.on_fail, r))

cmd = asm_cmd \
    ^ dw \
    ^ call \
    ^ struct \
    ^ ds \
    ^ ptr \
    ^ rptr \
    ^ item \
    ^ dt

statement = pp.Optional(label) + pp.Optional(comment) + cmd + pp.Optional(comment)
    
func_decl = (pp.Suppress("FUNC") + id).setParseAction(lambda r: (MFPP.issue_func, r)) + pp.Optional(comment)
func_local_var = pp.Suppress("DW") + pp.Optional(comment)
func_prologue = func_decl + pp.ZeroOrMore(func_local_var) + pp.Suppress("BEGIN")
func_epilogue = pp.Suppress("END") + pp.Optional(comment)
func = func_prologue + pp.ZeroOrMore(statement) + func_epilogue
    
program = pp.ZeroOrMore(statement ^ func ^ comment ^ unknown)