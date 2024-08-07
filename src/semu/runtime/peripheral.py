import logging as lg
import threading as th
import time
import socket
from typing import Mapping

import semu.common.hwconf as hw


class Peripheral(th.Thread):
    def __init__(self, memory: bytearray):
        super().__init__()
        self.memory = memory
        self.in_event = th.Event()
        self.out_event = th.Event()
        self.stop_event = th.Event()

    def stop(self):
        self.stop_event.set()
        self.out_event.set()

    def signal(self):
        self.out_event.set()
        time.sleep(0.01)

    def has_signal(self):
        if self.in_event.is_set():
            self.in_event.clear()
            return True
        else:
            return False

    def run(self):
        while True:
            self.out_event.wait()
            self.out_event.clear()

            if self.stop_event.is_set():
                self.stop_event.clear()
                self.on_stop()
                lg.debug('Peripheral stop')
                return

            self.process_in_signal()

    def process_in_signal(self):
        pass

    def on_stop(self):
        pass


class SysTimer(Peripheral):
    def __init__(self, memory: bytearray):
        super().__init__(memory)
        self.gen_signal = False      # Starts disactivated

    def start(self):
        super().start()
        self.restart_timer()

    def restart_timer(self):
        self.timer = th.Timer(1.0, self.on_timer)
        self.timer.start()

    def on_timer(self):
        self.restart_timer()

        if self.gen_signal:
            lg.debug('System timer')
            self.in_event.set()

    def process_in_signal(self):
        self.gen_signal = not self.gen_signal

    def on_stop(self):
        self.timer.cancel()


class Serial(Peripheral):
    def __init__(self, memory: bytearray):
        super().__init__(memory)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def process_in_signal(self):
        addr = hw.SERIAL_MM_BASE
        buf = self.memory[addr:addr + 4]
        self.sock.sendto(buf, (hw.CTL_SER_UDP_IP, hw.CTL_SER_UDP_PORT))
        time.sleep(hw.SERIAL_DELAY)


Peripherals = Mapping[int, Peripheral]
