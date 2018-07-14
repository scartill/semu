
memory_size      = 0xFFFF
int_vect_base    = 0x00000000
peripherals      = 16
int_vect_size    = peripherals*4
serial_rm_base   = int_vect_base + int_vect_size        # serial device mapped memory location
serial_rm_size   = 256
rom_base         = serial_rm_base + serial_rm_size

ctl_udp_ip = "127.0.0.1"
ctl_ser_udp_port = 5005     # port for serial device