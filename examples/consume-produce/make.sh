SEMU_ROOT="../.."
ASM=${SEMU_ROOT}"/src/semuasm.py"
ROM=${SEMU_ROOT}"/roms/consume-produce.bin"
LIB="../lib/kernel"

py ${ASM} ${LIB}/startup.sasm ${LIB}/kernel.sasm ${LIB}/api.sasm app.sasm ${ROM}
