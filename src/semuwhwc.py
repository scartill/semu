#!/usr/bin/python3

import hwconf as hw

def configure(param):
    value = hw.__dict__[param]
    print("CONST {0} {1}".format(param, value))
    
configure("INT_VECT_BASE")
configure("SERIAL_MM_BASE")
