$subject = "funcparams"

$compiler = "$PSScriptRoot/src/semu/pseudopython/compiler.py"
$assembler = "$PSScriptRoot/src/semu/sasm/masm.py"
$emulator = "$PSScriptRoot/src/semu/runtime/emulator.py"

$source = "$PSScriptRoot/examples/pseudopython/$subject.py"
$sasm = "$PSScriptRoot/.build/$subject.sasm"
$rom = "$PSScriptRoot/.build/$subject.bin"

python $compiler -v $source $sasm

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

# TODO: disable macroprocessor
python $assembler $sasm $rom

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

python $emulator $rom
