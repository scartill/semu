#!/usr/bin/python3

import sys
import logging as lg
import traceback

import peripheral
import cpu
import mmu

from hwconf import *

EXIT_HALT = 0
EXIT_ASSERT_FAIL = 1
EXIT_LAUNCH_FAIL = 2
EXIT_KEYBOARD = 3
EXIT_EXEC_ERROR = 100

def start_pp(pp):
    for _, p in pp.items():
        p.start()

def stop_pp(pp):
    for _, p in pp.items():
        p.stop()
        p.join()

def load_rom(memory):    
    rom = open(sys.argv[1], "rb").read()  
    rb = ROM_BASE
    l = len(rom)    
    memory[rb:rb+l] = rom    
        
def process_int_queue(pp, proc):
    for l, p in pp.items():
        if(p.has_signal()):
            proc.interrupt(l)
            break

def run():
    try:
        memory = bytearray(MEMORY_SIZE)
        mmunit = mmu.MMU(memory)
    
        # PERIPHERALS: Line -> Device
        pp = {
           #0 : loopback interrupt
            SYSTIMER_LINE : peripheral.SysTimer(memory),
            SERIAL_LINE : peripheral.Serial(memory)
        }

        proc = cpu.CPU(mmunit, pp)

        start_pp(pp)
        load_rom(memory)
    
        while(True):
            proc.exec_next()
            process_int_queue(pp, proc)
    except cpu.Halt:
        lg.info("Execution halted gracefully")
        return EXIT_HALT
    except cpu.Assert:
        lg.info("Execution halted on false assertion")
        return EXIT_ASSERT_FAIL
    except KeyboardInterrupt:
        lg.info("Execution halted by the user")
        return EXIT_KEYBOARD
    except Exception as e:
        lg.info("Execution halted on general error {0}".format(e))
        traceback.print_exc()
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



