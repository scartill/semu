import socket
import logging as lg
import struct
import sys

import semu.common.hwconf as hw

lg.basicConfig(level=lg.DEBUG)
lg.info('SEMU SERIAL')

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((hw.CTL_SER_UDP_IP, hw.CTL_SER_UDP_PORT))

while True:
    buf, _ = sock.recvfrom(1024)    # buffer size is 1024 bytes
    (word,) = struct.unpack('>I', buf)    
    sys.stdout.write(chr(word))
    sys.stdout.flush()
