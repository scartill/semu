SEMU_ROOT=".."
SEMU=$SEMU_ROOT"/src/semu.py"
ASM=$SEMU_ROOT"/src/semuasm.py"
WHWC=$SEMU_ROOT"/src/semuwhwc.py"
ROM=$SEMU_ROOT"/roms/test_run.bin"

function test_run {                                                   

    source $1.tst

    py $ASM $SRC $ROM
    if [[ $? != 0 ]]; then echo "Compilation failed for test case $1" && exit 1; fi

    rm -f .output
    py $SEMU $ROM > .output
    if [[ $? != 0 ]]; then echo "Test run failed (case $1)" && exit 1; fi
    
    if [[ $CMP == "" ]]; then echo "No output to compare (case $1)" && return 0; fi
    
    diff .output $CMP
    if [[ $? != 0 ]]; then echo "Test failed to create valid output (case $1)" && exit 1; fi
}

# Create definitions from hardware configuration
py $WHWC > hw.sasm

# Test if single test requested
if [[ $1 != "" ]]; then test_run $1 && exit 0; fi

test_run protmode/protmode
test_run mutex
test_run consts
test_run locals
echo "Passed successfully"


