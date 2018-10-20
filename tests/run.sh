SEMU_ROOT=".."
SEMU=${SEMU_ROOT}"/src/semu.py"
ASM=${SEMU_ROOT}"/src/semuasm.py"
WHWC=${SEMU_ROOT}"/src/semuwhwc.py"
ROM=${SEMU_ROOT}"/roms/test_run.bin"

function test_run {                                                   

    py ${ASM} `cat $1.tst` ${ROM}
    if [[ $? != 0 ]]; then echo "Compilation failed for test case $1" && exit 1; fi

    py ${SEMU} ${ROM}    
    if [[ $? != 0 ]]; then echo "Test failed (case $1)" && exit 1; fi
}

# Create definitions from hardware configuration
py ${WHWC} > hw.sasm

test_run consts
test_run locals
echo "Passed successfully"


