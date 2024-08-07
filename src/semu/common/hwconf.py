WORD_SIZE = 4   # do not change this value
MEMORY_SIZE = 0xFFFF
INT_VECT_BASE = 0x00000000
PERIPHERALS = 16
INT_VECT_SIZE = PERIPHERALS * WORD_SIZE
SERIAL_MM_BASE = INT_VECT_BASE + INT_VECT_SIZE  # serial device mapped memory location
SERIAL_MM_SIZE = 4
ROM_BASE = SERIAL_MM_BASE + SERIAL_MM_SIZE

LOOPBACK_LINE = 0
SYSTIMER_LINE = 1
SERIAL_LINE = 2

SERIAL_DELAY = 0.01			# Serial is much slower than UDP, that's it

CTL_IP = '127.0.0.1'		# By default run virtual devices on the localhost

CTL_SER_UDP_IP = CTL_IP     # IP for serial device
CTL_SER_UDP_PORT = 5005     # port for serial device
