# First-pass macroprocessor

import struct
import logging as lg

import ops
from fpp import FPP

# Abstract compilation context
class Context:
    pass
    
# Default global context
class GlobalContext(Context):
    def __init__(self):
        self.parent = self
        
    def ctxtype(self):
        return "global"
        
# Struct definition
class Struct(Context):
    def __init__(self, name, parent):
        self.parent = parent
        self.name = name
        self.fields = dict()
        self.size = 0                       # size in 4-byte words
        
    def ctxtype(self):
        return "struct"
        
    def add_field(self, name, width):
        lg.debug("Field {0}:{1}:{2}".format(name, width, self.size))
        self.fields[name] = self.size
        self.size += width
        
    def get_offset(self, fieldname):
        return self.fields[fieldname] * 4   # offset in bytes
        
class Func(Context):
    def __init__(self, name, parent):
        self.parent = parent
        self.name = name
        self.locals = dict()
        
    def ctxtype(self):
        return "func"
    
class MacroFPP(FPP):
    def __init__(self):
        FPP.__init__(self)
        self.context = GlobalContext()
        self.structs = dict()
        
    # Macros
    def issue_dw(self, tokens):
        self.on_label([tokens[0]])
        
        if(len(tokens) == 2):
            multipicity = int(tokens[1])
        else:
            multipicity = 1
        
        for _ in range(multipicity):
            self.issue_usigned(0x00000000)
        
    # CALL <func-ref>
    # Invalidates 'h'
    def issue_call(self, tokens):
        self.issue_op(ops.ldr)
        self.on_ref(tokens)
        self.on_reg(7)               # Using the last for routine address
        self.issue_op(ops.cll)
        self.on_reg(7)
    
    # FUNC <func-name>
    def begin_func(self, tokens):
        name = tokens[0]
        qname = self.get_qualified_name(name)
        
        if(self.context.ctxtype() != "global"):
            raise Exception("Cannot define non-global FUNC {0}", qname)
        self.context = Func(qname, self.context)
    
        self.on_label(tokens)        # Does nothing fancy really
        
    def func_local_var(self, tokens):
        pass
    
    def end_func(self, tokens):
        s = self.context
        self.context = s.parent
        
    # STRUCT <struct-type-name>
    def begin_struct(self, tokens):    
        name = tokens[0]
        qname = self.get_qualified_name(name)
        
        if(self.context.ctxtype() != "global"):
            raise Exception("Cannot define non-global STRUCT type")
        self.context = Struct(qname, self.context)
    
    # DW <field-name>
    def struct_field(self, tokens):
        type = tokens[0]
        fname = tokens[1]
        
        if(type == "DW"):
            width = 1
        else:
            raise Exception("Bad type {0}".format(type))
        
        s = self.context
        if(s.ctxtype() != "struct"):
            raise Exception("Unable to define STRUCT field outside a record")
            
        s.add_field(fname, width)
        
    # END
    def struct_end(self, tokens):    
        s = self.context
        if(s.ctxtype() != "struct"):
            raise Exception("Unable to define end STRUCT outside a record")
            
        self.structs[s.name] = s
        self.context = s.parent
        lg.debug("Struct {0}".format(s.name))
    
    # DS <type-name> <array-name> [* <size>]
    def issue_ds(self, tokens):
        qsname = self.resolve_name(tokens[0])        
        s = self.structs[qsname]
    
        name = tokens[1]
        
        if(len(tokens) == 3):
            multipicity = int(tokens[2])
        else:
            multipicity = 1
            
        words = s.size * multipicity
        self.on_label([name])
        # Issue placeholder-bytes
        for _ in range(words):
            self.issue_usigned(0x00000000)
    
    # PTR <struct-address-reg> <struct-type-name>#<field-name> <target-reg>
    # Invalidates 'g', 'h'
    def issue_ptr_head(self, tokens):
        self.issue_op(ops.mrr)
    
    # PTR <pointer-to-struct-address-reg> <struct-type-name>#<field-name> <target-reg>
    # Invalidates 'g', 'h'
    def issue_rptr_head(self, tokens):
        self.issue_op(ops.mmr)
    
    # Invalidates g, h
    def issue_ptr_tail(self, tokens):
        # before: partial command to to load struct address to reg
        # for PTR: mrr source-reg
        # for RPTR: mrm source-reg        
        fname = tokens[0]
        qsname = self.resolve_name(tokens[1])
        s = self.structs[qsname]
        offset = s.get_offset(fname)        
            
        self.on_reg(7)               # Using the last ('h') for struct address
        self.issue_op(ops.ldc)       # Loading the offset
        self.issue_usigned(offset)
        self.on_reg(6)               # Using 'g' for field offset
        self.issue_op(ops.add)       # Adding the offset
        self.on_reg(7)
        self.on_reg(6)
        # after: target reg
    
    # ITEM <struct-type-name-name>
    # Parameters: 'a' - array address, 'b' - index
    # Invalidates a, b, h
    # Returns a - item address
    def issue_item(self, tokens):
        # a - base
        # b - index
        qsname = self.resolve_name(tokens[0])
        s = self.structs[qsname]
        width = s.size*4
        # ldc <size> h
        self.issue_op(ops.ldc)
        self.issue_usigned(width)
        self.on_reg(7)
        # mul b h b
        self.issue_op(ops.mul)
        self.on_reg(1)
        self.on_reg(7)
        self.on_reg(1)
        # add a b a
        self.issue_op(ops.add)
        self.on_reg(0)
        self.on_reg(1)
        self.on_reg(0)

    # DT <text-name> "<string>"
    def issue_dt(self, tokens):
        self.on_label([tokens[0]])
        text = tokens[1]
        self.issue_usigned(len(text))
        for c in text.encode():
            self.issue_usigned(c)
