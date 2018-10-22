SEMU_ROOT="../.."
WHWC=${SEMU_ROOT}"/src/semuwhwc.py"
ASM=${SEMU_ROOT}"/src/semuasm.py"
ROM=${SEMU_ROOT}"/roms/twothreads.bin"
LIB="../lib/kernel"

# Create definitions from hardware configuration
py ${WHWC} > hw.sasm

# Compile with the Kernel
py ${ASM} hw.sasm ${LIB}/startup.sasm ${LIB}/sync.sasm ${LIB}/threads.sasm ${LIB}/kernel.sasm ${LIB}/api.sasm app.sasm ${ROM}
