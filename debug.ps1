$subject = "example"

$compiler = "$PSScriptRoot/src/semu/pseudopython/compiler.py"
$assembler = "$PSScriptRoot/src/semu/sasm/masm.py"
$emulator = "$PSScriptRoot/src/semu/runtime/emulator.py"

$examples = "$PSScriptRoot/examples/pseudopython"
$source = "$examples/$subject.py"
$sasm = "$PSScriptRoot/.build/$subject.sasm"
$rom = "$PSScriptRoot/.build/$subject.bin"

python $compiler -v --pp-path $examples $source $sasm

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# TODO: disable macroprocessor
python $assembler $sasm $rom

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python $emulator $rom
