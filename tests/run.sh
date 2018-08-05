SEMU_ROOT=".."
SEMU=${SEMU_ROOT}"/src/semu.py"
ASM=${SEMU_ROOT}"/src/semuasm.py"
ROM=${SEMU_ROOT}"/roms/test_run.bin"

function test_run {
    py ${ASM} $1.sasm ${ROM}
    py ${SEMU} ${ROM} || (echo "Test failed (case $1)" && exit 1)
}

test_run locals
echo "Passed successfully"


