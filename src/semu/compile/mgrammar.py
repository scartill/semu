import pyparsing as pp

import semu.common.ops as ops
from semu.compile.mfpp import MacroFPP as MFPP

from semu.compile.grammar import *

# Simple macros
multi = pp.Optional(pp.Suppress("*") + pp.Regex("[1-9][0-9]*"))
dw = (pp.Suppress("DW") + id + multi).setParseAction(lambda r: (MFPP.issue_dw, r))
call = (pp.Suppress("CALL") + refname).setParseAction(lambda r: (MFPP.issue_call, r))

# Macro-struct
struct_begin = (pp.Suppress("STRUCT") + id).setParseAction(lambda r: (MFPP.begin_struct, r))
field_type = pp.Or(pp.Literal("DW"))
struct_field = (field_type + id + pp.Optional(comment)).setParseAction(lambda r: (MFPP.struct_field, r))
struct_end = pp.Suppress("END").setParseAction(lambda r: (MFPP.struct_end, r))
struct = struct_begin + pp.OneOrMore(struct_field) + struct_end

ds = (pp.Suppress("DS") + refname + id + multi).setParseAction(lambda r: (MFPP.issue_ds, r))

# Indirect references
ptr_head = pp.Literal("PTR").setParseAction(lambda r: (MFPP.issue_ptr_head, r))
ptr_tail = (id + pp.Suppress("#") + refname).setParseAction(lambda r: (MFPP.issue_ptr_tail, r))
ptr = ptr_head + reg_op + ptr_tail + reg_op

# Array access
item = (pp.Suppress("ITEM") + refname).setParseAction(lambda r: (MFPP.issue_item, r))

# Text array
dt = (pp.Suppress("DT") + id + pp.QuotedString('"')).setParseAction(lambda r: (MFPP.issue_dt, r))

# Auto variable support
func_return = pp.Suppress("RETURN").setParseAction(lambda r: (MFPP.func_return, r))
local_store = (pp.Suppress("LSTORE") + reg_ref + id).setParseAction(lambda r: (MFPP.local_store, [reg_indices[r[0]], r[1]]))
local_load = (pp.Suppress("LLOAD") + id + reg_ref).setParseAction(lambda r: (MFPP.local_load, [r[0], reg_indices[r[1]]]))

# Macro constants
m_uint_const = pp.Regex("[0-9]+")
const_def = (pp.Suppress("CONST") + id + m_uint_const).setParseAction(lambda r: (MFPP.const_def, r))
const_load = (pp.Suppress("CLOAD") + refname + reg_ref).setParseAction(lambda r: (MFPP.const_load, [r[0], reg_indices[r[1]]]))

# Fail on unknown command
unknown = pp.Regex(".+").setParseAction(lambda r: (MFPP.on_fail, r))

cmd = asm_cmd \
    ^ dw \
    ^ call \
    ^ struct \
    ^ ds \
    ^ ptr \
    ^ item \
    ^ dt \
    ^ func_return \
    ^ local_store \
    ^ local_load \
    ^ const_def \
    ^ const_load

statement = pp.Optional(label) + pp.Optional(comment) + cmd + pp.ZeroOrMore(comment)
    
func_decl = (pp.Suppress("FUNC") + id).setParseAction(lambda r: (MFPP.begin_func, r)) + pp.Optional(comment)
func_var_def = pp.Suppress("DW") + id + reg_ref + pp.Suppress(pp.Optional(comment))
func_var = func_var_def.setParseAction(lambda r: (MFPP.func_var, [r[0], reg_indices[r[1]]]))
func_prologue = func_decl + pp.ZeroOrMore(func_var) + pp.Suppress("BEGIN")
func_epilogue = pp.Suppress("END").setParseAction(lambda r: (MFPP.end_func, r)) + pp.Optional(comment)
func = func_prologue + pp.ZeroOrMore(statement) + func_epilogue
    
program = pp.ZeroOrMore(statement ^ func ^ comment ^ unknown)