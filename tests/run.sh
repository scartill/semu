SEMU_ROOT=".."
SEMU=${SEMU_ROOT}"/src/semu.py"
ASM=${SEMU_ROOT}"/src/semuasm.py"
ROM=${SEMU_ROOT}"/roms/test_run.bin"

function test_run {
    py ${ASM} $1.sasm ${ROM}
    if [[ $? != 0 ]]; then echo "Compilation failed for test case $1" && return 1; fi

    py ${SEMU} ${ROM}    
    if [[ $? != 0 ]]; then echo "Test failed (case $1)" && return 1; fi
}

test_run consts || exit $?
test_run locals || exit $?
echo "Passed successfully"


