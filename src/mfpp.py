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
        self.locals = []
        self.has_return = False
        
    def ctxtype(self):
        return "func"
    
class MacroFPP(FPP):
    def __init__(self):
        FPP.__init__(self)
        self.context = GlobalContext()
        self.structs = dict()
        self.consts = dict()
        
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
        self.context = Func(name, self.context)
    
        self.on_label(tokens)        # Does nothing fancy really
        
    # Inside FUNC:
    #   DW <var-name> <init_reg>    
    def func_var(self, tokens):
        func = self.context
        if(func.ctxtype() != "func"):
            raise Exception("Unable to define local variable outside a function")
        
        vname = tokens[0]
        reg = tokens[1]
        
        if vname in func.locals:
            raise Exception("Duplicate local variable declaration")
            
        func.locals.append(vname)
        
        # push <reg>
        self.issue_op(ops.psh)
        self.on_reg(reg)
        
    # Inside FUNC:
    #   END
    def func_return(self, tokens):
        func = self.context
        if(func.ctxtype() != "func"):
            raise Exception("Unexpected RETURN macro")
            
        func.has_return = True
        
        # Go to <func-name>:prologue
        pname = func.name + ":prologue"
        
        # ldr &name:prologue h
        self.issue_op(ops.ldr)
        self.on_ref([[pname]])
        self.on_reg(7)
        
        # jmp h
        self.issue_op(ops.jmp)
        self.on_reg(7)
    
    # Inside FUNC:
    #   END
    def end_func(self, tokens):
        func = self.context
        if(func.ctxtype() != "func"):
            raise Exception("Unexpected function end")
            
        if not func.has_return:
            raise Exception("Function END without RETURN ({0})".format(func.name))
        
        pname = func.name + ":prologue"
        self.on_label([pname])
        
        # pop h
        # ...
        # pop h
        # ret
        for _ in func.locals:
            self.issue_op(ops.pop)
            self.on_reg(7)              # Dumping values to 'h'
        
        self.issue_op(ops.ret)
        
        # Restore global context
        self.context = func.parent
        
    # LSTORE <reg> <var-name>
    # Invalidates 'h'
    def local_store(self, tokens):
        func = self.context
        if(func.ctxtype() != "func"):
            raise Exception("Unexpected LSTORE macro")
    
        reg = tokens[0]
        vname = tokens[1]        
        
        offset = func.locals.index(vname) * 4
        lg.debug("Local store {0}@{1}".format(vname, offset))
        
        # lla <var-offset> h
        # mrm <reg> h
        self.issue_op(ops.lla)
        self.issue_usigned(offset)
        self.on_reg(7)
        self.issue_op(ops.mrm)
        self.on_reg(reg)
        self.on_reg(7)
        
    # LLOAD <var-name> <reg>
    # Invalidates 'h'
    def local_load(self, tokens):
        func = self.context
        if(func.ctxtype() != "func"):
            raise Exception("Unexpected LLOAD macro")
    
        vname = tokens[0]
        reg = tokens[1]
        
        offset = func.locals.index(vname) * 4
        lg.debug("Local load {0}@{1}".format(vname, offset))
        
        # lla <var-offset> h
        # mmr h <reg>
        self.issue_op(ops.lla)
        self.issue_usigned(offset)
        self.on_reg(7)
        self.issue_op(ops.mmr)
        self.on_reg(7)
        self.on_reg(reg)        
        
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
    
    # Invalidates g, h
    def issue_ptr_tail(self, tokens):
        # <before>: partial command to to load struct address to reg
        # for PTR: mrr source-reg
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
        # <after>: target reg
    
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

    # CONST <name> <integer>
    def const_def(self, tokens):
        name = tokens[0]
        value = int(tokens[1])      # Integer constants support
        qname = self.get_qualified_name(name)
        
        if(self.context.ctxtype() != "global"):
            raise Exception("Cannot define non-global CONST {0}", qname)
            
        self.consts[qname] = value
        lg.debug("Constant {0}={1}".format(qname, value))
        
    # CLOAD <const-name> <reg>
    # Invalidates <reg>
    def const_load(self, tokens):  
        qsname = self.resolve_name(tokens[0])
        value = self.consts[qsname]
        reg = tokens[1]
        # ldc <const> <reg>
        self.issue_op(ops.ldc)
        self.issue_usigned(value)
        self.on_reg(reg)
        
