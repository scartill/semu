#!/usr/bin/python3

import sys
import logging as lg

import peripheral
import cpu

from hwconf import *

EXIT_HALT = 0
EXIT_ASSERT_FAIL = 1
EXIT_LAUNCH_FAIL = 2
EXIT_EXEC_ERROR = 3

### Global ###

def start_pp(pp):
    for l, p in pp.items():
        p.start()

def stop_pp(pp):
    for l, p in pp.items():
        p.stop()
        p.join()

def load_rom(memory):    
    rom = open(sys.argv[1], "rb").read()  
    rb = rom_base
    l = len(rom)    
    memory[rb:rb+l] = rom    
        
def process_int_queue(pp, proc):
    for l, p in pp.items():
        if(p.has_signal()):
            proc.interrupt(l)
            break

def run():
    memory = bytearray(memory_size)
    
    # Peripherals: Line -> Device
    pp = {
       #0 : loopback interrupt
        1 : peripheral.SysTimer(memory),
        2 : peripheral.Serial(memory)
    }

    proc = cpu.CPU(memory, pp)

    start_pp(pp)
    load_rom(memory)
    
    try:
        while(True):
            proc.exec_next()
            process_int_queue(pp, proc)
    except cpu.Halt:
        lg.info("Execution halted gracefully")
        return EXIT_HALT
    except cpu.Assert:
        lg.info("Execution halted on false assertion")
        return EXIT_ASSERT_FAIL
    except Exception as e:
        lg.info("Execution halted on general error {0}".format(e))
        return EXIT_EXEC_ERROR
    finally:
        stop_pp(pp)

### Entry point ###

if len(sys.argv) != 2:
    print("Usage: semu rom-binary")
    sys.exit(EXIT_LAUNCH_FAIL)

lg.basicConfig(level = lg.DEBUG)
lg.info("SEMU")

ec = run()
sys.exit(ec)



