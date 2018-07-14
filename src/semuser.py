import socket
import logging as lg
import struct
import sys

import hwconf as hw

lg.basicConfig(level = lg.DEBUG)
lg.info("SEMU SERIAL")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((hw.ctl_udp_ip, hw.ctl_ser_udp_port))

while True:
    buf, _ = sock.recvfrom(1024) # buffer size is 1024 bytes
    (word,) = struct.unpack(">I", buf)    
    sys.stdout.write(chr(word))
    sys.stdout.flush()
    