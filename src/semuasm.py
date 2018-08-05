#!/usr/bin/python3

import sys
import os
import logging as lg
import struct

import mfpp
import mgrammar

def namespace(in_filename):
    basename = os.path.basename(in_filename)
    sname, _ = os.path.splitext(basename)
    return sname

def compile(in_filenames, out_filename):    
    # First pass
    first_pass = mfpp.MacroFPP()        
    for in_filename in in_filenames:
        lg.info("Processing {0}".format(in_filename))
        first_pass.namespace = namespace(in_filename)
        actions = mgrammar.program.parseFile(in_filename)
        for (func, arg) in actions:
            func(first_pass, arg)
    
    # Second pass
    bytestr = bytearray()
    for (t, d) in first_pass.cmd_list:
        if t == 'bytes':
            bytestr += d
                
        if t == 'ref':
            (ref_offset, labelname) = d
            label_offset = first_pass.label_dict[labelname]
            offset = label_offset - ref_offset
            bytestr += struct.pack(">i", offset)

    # Dumping results
    open(out_filename, "wb").write(bytestr)
   
argc = len(sys.argv)
if argc < 3:
    print("Usage: semuasm <sources> binary")
    sys.exit(1)

lg.basicConfig(level=lg.INFO)
lg.info("SEMU ASM")
compile(sys.argv[1:(argc - 1)], sys.argv[argc - 1])
