SEMU_ROOT="../.."
WHWC=${SEMU_ROOT}"/src/semuwhwc.py"
ASM=${SEMU_ROOT}"/src/semuasm.py"
ROM=${SEMU_ROOT}"/roms/twothreads.bin"

# Create definitions from hardware configuration
py ${WHWC} > hw.sasm

# Add kernel to compilcation
source $SEMU_ROOT/lib/kernel/build.list

# Compile with the Kernel
py ${ASM} hw.sasm $KERNEL_SRC app.sasm ${ROM}
