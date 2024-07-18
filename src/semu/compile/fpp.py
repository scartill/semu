import struct
import logging as lg


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
