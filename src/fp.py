
import struct
import logging as lg

import ops

# Struct definition
class Struct:
    def __init__(self, name):
        self.name = name
        self.fields = dict()
        self.size = 0                       # size in 4-byte words
        
    def add_field(self, name, width):
        lg.debug("Field {0}:{1}:{2}".format(name, width, self.size))
        self.fields[name] = self.size
        self.size += width
        
    def get_offset(self, fieldname):
        return self.fields[fieldname] * 4   # offset in bytes

# First pass processor
class FPP:
    def __init__(self):
        self.cmd_list = list()
        self.offset = 0
        self.namespace = "<global>"
        self.label_dict = dict()
        
    def get_qualified_name(self, name, namespace = None):    
        if(namespace == None):
            namespace = self.namespace    
        return namespace + "::" + name
        
    def resolve_name(self, tokens):
        if(len(tokens) == 1):
            # Unqualified
            name = self.get_qualified_name(tokens[0])
        else:
            # Qualified
            name = self.get_qualified_name(tokens[1], tokens[0]) # name, namespace        
            
        return name

    # Handlers
    def issue_word(self, fmt, word):
        bytestr = struct.pack(fmt, word)
        self.cmd_list.append(('bytes', bytestr))
        self.offset += 4

    def issue_usigned(self, word):        
        self.issue_word(">I", word)

    def issue_signed(self, word):
        self.issue_word(">i", word)

    def issue_op(self, op):
        lg.debug("Issuing command 0x{0:X}".format(op))
        self.issue_usigned(op)
        
    def on_uconst(self, tokens):
        word = int(tokens[0])
        self.issue_usigned(word)
        
    def on_sconst(self, tokens):
        word = int(tokens[0])
        self.issue_signed(word)        

    def on_label(self, tokens):
        labelname = tokens[0]
        qlabelname = self.get_qualified_name(labelname)
        self.label_dict[qlabelname] = self.offset
        lg.debug("Label {0} @ 0x{1:X}".format(qlabelname, self.offset))

    def on_reg(self, val):
        self.issue_usigned(val)
    
    def on_ref(self, tokens):
        labelname = self.resolve_name(tokens[0])
        lg.debug("Ref {0}".format(labelname))
        
        current_offset = self.offset
        self.cmd_list.append(('ref', (current_offset, labelname)))
        self.offset += 4 # placeholder-bytes        

    def on_fail(self, r):
        raise Exception("Unknown command {0}".format(r))
    
class MacroFPP(FPP):
    def __init__(self):
        FPP.__init__(self)
        self.context = None
        self.structs = dict()
        
    # Macros
    def macro_issue_dw(self, tokens):
        self.on_label([tokens[0]])
        
        if(len(tokens) == 2):
            multipicity = int(tokens[1])
        else:
            multipicity = 1
        
        for _ in range(multipicity):
            self.issue_usigned(0x00000000)
        
    def macro_issue_call(self, tokens):
        self.issue_op(ops.ldr)
        self.on_ref(tokens)
        self.on_reg(7)               # Using the last for routine address
        self.issue_op(ops.cll)
        self.on_reg(7)
    
    def macro_issue_func(self, tokens):
        self.on_label(tokens)        # Does nothing fancy really
        
    def macro_begin_struct(self, tokens):    
        name = tokens[0]
        qname = self.get_qualified_name(name)
        
        if(self.context != None):
            raise Exception("Bad context")
        self.context = Struct(qname)
        
    def macro_struct_field(self, tokens):
        type = tokens[0]
        fname = tokens[1]
        
        if(type == "DW"):
            width = 1
        else:
            raise Exception("Bad type {0}".format(type))
        
        s = self.context
        if(s == None):
            raise Exception("Bad context")
            
        s.add_field(fname, width)        
        
    def macro_struct_end(self, tokens):    
        s = self.context
        if(self.context == None):
            raise Exception("Bad context")
            
        self.structs[s.name] = s
        self.context = None
        lg.debug("Struct {0}".format(s.name))
        
    def macro_issue_ds(self, tokens):
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
            
    def macro_issue_ptr_head(self, tokens):
        self.issue_op(ops.mrr)
    
    def macro_issue_rptr_head(self, tokens):
        self.issue_op(ops.mmr)
    
    # Invalidates g, h
    def macro_issue_ptr_tail(self, tokens):
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
    
    # Invalidates a, b, h
    # Returns a
    def macro_issue_item(self, tokens):
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

    def macro_issue_dt(self, tokens):
        self.on_label([tokens[0]])
        text = tokens[1]
        self.issue_usigned(len(text))
        for c in text.encode():
            self.issue_usigned(c)
