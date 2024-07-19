import sys
from pathlib import Path
import logging as lg
import traceback

import click

from semu.common.hwconf import MEMORY_SIZE, SYSTIMER_LINE, SERIAL_LINE, ROM_BASE
from semu.runtime.peripheral import Peripherals, SysTimer, Serial
import semu.runtime.cpu as cpu


EXIT_HALT = 0
EXIT_ASSERT_FAIL = 2
EXIT_KEYBOARD = 3
EXIT_EXEC_ERROR = 100


def start_pp(pp: Peripherals):
    for p in pp.values():
        p.start()


def stop_pp(pp: Peripherals):
    for p in pp.values():
        p.stop()
        p.join()


def init_memory(memory: bytearray, rom: bytes):
    rb = ROM_BASE
    mem_len = len(memory)
    memory[rb:rb + mem_len] = rom


def process_int_queue(pp: Peripherals, proc: cpu.CPU):
    for line, peripheral in pp.items():
        if peripheral.has_signal():
            proc.interrupt(line)
            break


def execute(rom: bytes):
    pp = None

    try:
        memory = bytearray(MEMORY_SIZE)

        # PERIPHERALS: Line -> Device
        pp = {
            # 0 : loopback interrupt
            SYSTIMER_LINE: SysTimer(memory),
            SERIAL_LINE: Serial(memory)
        }

        proc = cpu.CPU(memory, pp)

        start_pp(pp)
        init_memory(memory, rom)

        while True:
            proc.exec_next()
            process_int_queue(pp, proc)

    finally:
        # TODO: make peripherals' constructors finally-friendly
        if pp is not None:
            stop_pp(pp)


@click.command()
@click.argument('rom_filename', type=Path)
def run(rom_filename: Path):
    lg.basicConfig(level=lg.DEBUG)
    lg.info("SEMU")

    try:
        rom = rom_filename.read_bytes()
        sys.exit(execute(rom))

    except cpu.Halt:
        lg.info('Execution halted gracefully')
        sys.exit(EXIT_HALT)

    except cpu.Assert:
        lg.info('Execution halted on false assertion')
        sys.exit(EXIT_ASSERT_FAIL)

    except KeyboardInterrupt:
        lg.info('Execution halted by the user')
        return sys.exit(EXIT_KEYBOARD)

    except Exception as e:
        lg.info(f'Execution halted on general error {e}')
        traceback.print_exc()
        return sys.exit(EXIT_EXEC_ERROR)


if __name__ == '__main__':
    run()
