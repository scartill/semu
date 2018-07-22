SEMU_ROOT=".."
SEMU=${SEMU_ROOT}"/src/semu.py"
ASM=${SEMU_ROOT}"/src/semuasm.py"
ROM=${SEMU_ROOT}"/roms/test_run.bin"

py ${ASM} locals.sasm ${ROM}
py ${SEMU} ${ROM}
